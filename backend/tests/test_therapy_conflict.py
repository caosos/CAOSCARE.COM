"""careops-therapy-conflict-001: overlapping planned work for one resident is
detected, refused unless staff save anyway, and the override is receipted.

    TEST_API_BASE=http://127.0.0.1:8070 pytest tests/test_therapy_conflict.py -q
"""
import asyncio
import os
import sys
import uuid
from datetime import date, timedelta

import bcrypt
import pytest
import requests

BASE_URL = os.environ.get("TEST_API_BASE", os.environ.get("REACT_APP_BACKEND_URL", "http://127.0.0.1:8000")).rstrip("/")
API = f"{BASE_URL}/api"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TAG = f"thc_{uuid.uuid4().hex[:8]}"


def _backend_up() -> bool:
    try:
        requests.get(f"{API}/health", timeout=3).raise_for_status()
        return True
    except Exception:
        return False


def _login(email, pw):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": pw}, timeout=5)
    r.raise_for_status()
    return {"Authorization": f"Bearer {r.json()['token']}"}


def _ok(r):
    assert r.status_code == 200, (r.status_code, r.text)
    return r.json()


async def _run():
    from motor.motor_asyncio import AsyncIOMotorClient
    from models import uid, now_utc
    from routes.realtime_facility import today_facility_date
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    pw = "thc-pw-12345678"
    people = {"fd": ("front_desk", None), "pt": ("staff", "therapy"), "nurse": ("staff", "nursing"), "admin": ("admin", None)}
    ids = {}
    for k, (role, dept) in people.items():
        ids[k] = uid("user")
        await db.users.insert_one({"user_id": ids[k], "email": f"{TAG}_{k}@example.com", "name": f"{TAG} {k}", "role": role,
                                   "department": dept, "auth_provider": "jwt", "created_at": now_utc().isoformat(),
                                   "password_hash": bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()})
    if not await db.departments.find_one({"slug": "therapy"}):
        await db.departments.insert_one({"department_id": uid("dept"), "slug": "therapy", "label": "Therapy", "active": True,
                                         "created_at": now_utc().isoformat(), "_tag": TAG})
    room = f"{TAG}-R"
    rid = uid("res")
    await db.residents.insert_one({"resident_id": rid, "name": f"{TAG} Resident", "preferred_name": "Pat", "room": room, "created_at": now_utc().isoformat()})
    d1 = (date.fromisoformat(today_facility_date()) + timedelta(days=2)).isoformat()
    try:
        H = {k: _login(f"{TAG}_{k}@example.com", pw) for k in people}

        def ask(summary, category="therapy"):
            return _ok(requests.post(f"{API}/tasks/resident-request", headers=H["fd"], json={
                "category": category, "resident_id": rid, "source": "front_desk", "summary": summary, "resident_words": summary}, timeout=5))["task_id"]

        def plan(t, who, **body):
            return requests.patch(f"{API}/tasks/{t}", headers=H[who], json=body, timeout=5)

        a = ask("Knee physical therapy"); _ok(plan(a, "pt", requested_for_date=d1, requested_for_time_label="2:00 PM"))
        b = ask("Hip strength session")
        chain_before = await db.receipts.count_documents({"related_object_id": b})

        # non-overlap is saved without fuss (3:00 PM starts exactly when the 60-min slot ends)
        _ok(plan(b, "pt", requested_for_date=d1, requested_for_time_label="3:00 PM"))
        # preview says what would overlap
        chk = _ok(requests.get(f"{API}/tasks/{b}/conflicts", headers=H["pt"], params={"requested_for_time_label": "2:30 PM"}, timeout=5))
        assert chk["checked"] and [c["task_id"] for c in chk["conflicts"]] == [a] and chk["conflicts"][0]["what"] == "Knee physical therapy"
        clear = _ok(requests.get(f"{API}/tasks/{b}/conflicts", headers=H["pt"], timeout=5))
        assert clear["checked"] and clear["conflicts"] == []

        # overlap is refused with the conflicts; nothing written
        r = plan(b, "pt", requested_for_time_label="2:30 PM")
        assert r.status_code == 409 and r.json()["detail"]["code"] == "schedule_conflict", r.text
        assert [c["task_id"] for c in r.json()["detail"]["conflicts"]] == [a]
        doc = await db.staff_tasks.find_one({"task_id": b}, {"_id": 0})
        assert doc["requested_for_time_label"] == "3:00 PM"
        assert await db.receipts.count_documents({"related_object_id": b}) == chain_before + 1   # only the 3:00 PM plan receipt

        # save anyway: written, event text names the overlap, receipt records the override
        _ok(plan(b, "pt", requested_for_time_label="2:30 PM", conflict_override=True))
        doc = await db.staff_tasks.find_one({"task_id": b}, {"_id": 0})
        assert doc["requested_for_time_label"] == "2:30 PM"
        ev = [e for e in doc["event_log"] if e["field"] == "scheduled"][-1]
        assert "saved despite overlapping Knee physical therapy (2:00 PM)" in ev["text"]
        rc = await db.receipts.find_one({"receipt_id": ev["receipt_id"]}, {"_id": 0})
        assert rc["action_type"] == "task_schedule_updated" and rc["result"] == "conflict_override" and rc["provider_refs"] == [a]
        assert rc["authority"] == "acts_for:therapy" and rc["before_state"]["requested_for_time_label"] == "3:00 PM" and rc["after_state"]["requested_for_time_label"] == "2:30 PM"
        # the upcoming view shows both sides of the overlap
        up = {i["task_id"]: i for i in _ok(requests.get(f"{API}/tasks/upcoming", headers=H["pt"], params={"department": "therapy"}, timeout=5))["items"]}
        assert [c["task_id"] for c in up[a]["conflicts"]] == [b] and [c["task_id"] for c in up[b]["conflicts"]] == [a]
        # a note-only PATCH and a details-only PATCH never trip the check
        _ok(plan(b, "pt", notes="bring the resistance bands")); _ok(plan(b, "pt", location="Gym"))

        # unreadable time: saved, but honestly "not checked" (never "no conflict")
        c = ask("Speech therapy"); _ok(plan(c, "pt", requested_for_date=d1, requested_for_time_label="afternoon"))
        chk = _ok(requests.get(f"{API}/tasks/{c}/conflicts", headers=H["pt"], timeout=5))
        assert chk["checked"] is False and "not checked" in chk["reason"]
        up = {i["task_id"]: i for i in _ok(requests.get(f"{API}/tasks/upcoming", headers=H["pt"], params={"department": "therapy"}, timeout=5))["items"]}
        assert up[c]["conflicts"] == [] and up[c]["conflict_check"]
        chk_a = _ok(requests.get(f"{API}/tasks/{a}/conflicts", headers=H["pt"], timeout=5))
        assert [u["task_id"] for u in chk_a["undetermined"]] == [c]

        # cross-department: a nursing visit at 2:15 PM overlaps the therapy appointment too (same resident)
        n = ask("Wound check", category="nursing"); _ok(plan(n, "nurse", requested_for_date=d1, requested_for_time_label="2:15 PM", conflict_override=True))
        chk_a = _ok(requests.get(f"{API}/tasks/{a}/conflicts", headers=H["pt"], timeout=5))
        assert {u["task_id"] for u in chk_a["conflicts"]} == {b, n}

        # linked ride still follows an overridden reschedule
        ride = _ok(requests.post(f"{API}/tasks/{a}/ride", headers=H["pt"], timeout=5))["task_id"]
        _ok(plan(a, "pt", requested_for_time_label="2:45 PM", conflict_override=True))
        rd = await db.staff_tasks.find_one({"task_id": ride}, {"_id": 0})
        assert rd["requested_for_time_label"] == "2:45 PM" and rd["status"] != "skipped"
        # the appointment's ride is not a separate overlap against the other appointment
        chk_b = _ok(requests.get(f"{API}/tasks/{b}/conflicts", headers=H["pt"], timeout=5))
        assert ride not in {u["task_id"] for u in chk_b["conflicts"]} and a in {u["task_id"] for u in chk_b["conflicts"]}
        # but a standalone ride (no appointment behind it) does count - on a day with no other ride,
        # since the transportation core keeps one open ride per resident per day
        d_other = (date.fromisoformat(d1) + timedelta(days=1)).isoformat()
        x = ask("Range of motion check"); _ok(plan(x, "pt", requested_for_date=d_other, requested_for_time_label="2:00 PM"))
        solo = _ok(requests.post(f"{API}/transportation/staff/request", headers=H["fd"], json={
            "resident_id": rid, "purpose": "pharmacy run", "requested_for_date": d_other, "requested_for_time_label": "2:30 PM"}, timeout=5))
        solo_id = solo.get("task_id") or solo.get("request", {}).get("task_id")
        chk_x = _ok(requests.get(f"{API}/tasks/{x}/conflicts", headers=H["pt"], timeout=5))
        assert [u["task_id"] for u in chk_x["conflicts"]] == [solo_id], chk_x

        # authorization: nursing cannot read a therapy request's conflicts; front desk cannot plan it (409 or 403 never writes)
        assert requests.get(f"{API}/tasks/{a}/conflicts", headers=H["nurse"], timeout=5).status_code == 403
        r = plan(a, "fd", requested_for_time_label="2:00 PM"); assert r.status_code == 403, r.text
        assert requests.get(f"{API}/tasks/{a}/conflicts", timeout=5).status_code == 401
        # closed work does not count
        _ok(requests.post(f"{API}/tasks/{n}/start", headers=H["nurse"], timeout=5))
        _ok(requests.post(f"{API}/tasks/{n}/complete", headers=H["nurse"], json={"notes": "done"}, timeout=5))
        chk_a = _ok(requests.get(f"{API}/tasks/{a}/conflicts", headers=H["pt"], timeout=5))
        assert {u["task_id"] for u in chk_a["conflicts"]} == {b}
    finally:
        await db.users.delete_many({"email": {"$regex": f"^{TAG}_"}})
        await db.departments.delete_many({"_tag": TAG})
        await db.residents.delete_many({"resident_id": rid})
        tids = [t["task_id"] for t in await db.staff_tasks.find({"resident_id": rid}, {"task_id": 1}).to_list(50)]
        await db.staff_tasks.delete_many({"task_id": {"$in": tids}})
        await db.receipts.delete_many({"related_object_id": {"$in": tids}})
        await db.notifications.delete_many({"related_object_id": {"$in": tids}})


@pytest.mark.skipif(not _backend_up(), reason="backend not running")
def test_schedule_conflicts_detected_refused_and_overridden_with_receipt():
    asyncio.run(_run())
