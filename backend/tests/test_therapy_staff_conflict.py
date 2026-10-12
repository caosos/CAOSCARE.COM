"""careops-therapy-staff-conflict-001: the same provider or staff member double-booked across residents.
Detected, refused unless staff save anyway, and the override is receipted.

    TEST_API_BASE=http://127.0.0.1:8070 pytest tests/test_therapy_staff_conflict.py -q
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
TAG = f"tsc_{uuid.uuid4().hex[:8]}"


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
    pw = "tsc-pw-12345678"
    people = {"fd": ("front_desk", None), "pt": ("staff", "therapy"), "pt2": ("staff", "therapy"),
              "nurse": ("staff", "nursing"), "admin": ("admin", None)}
    ids = {}
    for k, (role, dept) in people.items():
        ids[k] = uid("user")
        await db.users.insert_one({"user_id": ids[k], "email": f"{TAG}_{k}@example.com", "name": f"{TAG} {k}", "role": role,
                                   "department": dept, "auth_provider": "jwt", "created_at": now_utc().isoformat(),
                                   "password_hash": bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()})
    if not await db.departments.find_one({"slug": "therapy"}):
        await db.departments.insert_one({"department_id": uid("dept"), "slug": "therapy", "label": "Therapy", "active": True,
                                         "created_at": now_utc().isoformat(), "_tag": TAG})
    rids = []
    for i in range(3):
        r = uid("res"); rids.append(r)
        await db.residents.insert_one({"resident_id": r, "name": f"{TAG} Resident {i}", "preferred_name": f"R{i}",
                                       "room": f"{TAG}-{i}", "created_at": now_utc().isoformat()})
    d1 = (date.fromisoformat(today_facility_date()) + timedelta(days=2)).isoformat()
    try:
        H = {k: _login(f"{TAG}_{k}@example.com", pw) for k in people}

        def ask(rid, summary):
            return _ok(requests.post(f"{API}/tasks/resident-request", headers=H["fd"], json={
                "category": "therapy", "resident_id": rid, "source": "front_desk", "summary": summary,
                "resident_words": summary}, timeout=5))["task_id"]

        def plan(t, who="pt", **body):
            return requests.patch(f"{API}/tasks/{t}", headers=H[who], json=body, timeout=5)

        a = ask(rids[0], "Knee therapy")
        _ok(plan(a, provider_name="Tess Ortiz PT", requested_for_date=d1, requested_for_time_label="10:00 AM"))
        b = ask(rids[1], "Gait training")
        before = await db.receipts.count_documents({"related_object_id": b})

        # different provider, same time, other resident: no conflict
        _ok(plan(b, provider_name="Sam Lee OT", requested_for_date=d1, requested_for_time_label="10:00 AM"))
        # same provider (different case/spacing) at an overlapping time: refused, nothing written
        r = plan(b, provider_name="  tess  ORTIZ pt ", requested_for_time_label="10:30 AM")
        assert r.status_code == 409 and r.json()["detail"]["code"] == "schedule_conflict", r.text
        cf = r.json()["detail"]["conflicts"]
        assert [c["task_id"] for c in cf] == [a] and cf[0]["kind"] == "staff" and "Tess Ortiz PT" in cf[0]["shared"]
        doc = await db.staff_tasks.find_one({"task_id": b}, {"_id": 0})
        assert doc["provider_name"] == "Sam Lee OT" and doc["requested_for_time_label"] == "10:00 AM"
        assert await db.receipts.count_documents({"related_object_id": b}) == before + 2   # details + schedule only
        # a provider-only change onto a planned slot is checked too
        r = plan(b, provider_name="Tess Ortiz PT")
        assert r.status_code == 409, r.text
        # same provider, non-overlapping (11:00 starts when the 60-min slot ends): saved
        _ok(plan(b, provider_name="Tess Ortiz PT", requested_for_time_label="11:00 AM"))
        # unauthorized callers learn nothing and write nothing
        for who in ("nurse", "fd"):
            assert plan(b, who, requested_for_time_label="10:30 AM").status_code == 403
        # save anyway: written; receipt and history record the override and the other request
        _ok(plan(b, requested_for_time_label="10:30 AM", conflict_override=True))
        doc = await db.staff_tasks.find_one({"task_id": b}, {"_id": 0})
        ev = [e for e in doc["event_log"] if e["field"] == "scheduled"][-1]
        assert "saved despite overlapping Knee therapy (10:00 AM)" in ev["text"]
        rc = await db.receipts.find_one({"receipt_id": ev["receipt_id"]}, {"_id": 0})
        assert rc["result"] == "conflict_override" and rc["provider_refs"] == [a] and rc["authority"] == "acts_for:therapy"
        # details-only override is recorded on the details receipt
        c = ask(rids[2], "Balance class")
        _ok(plan(c, provider_name="Pat Kim PT", requested_for_date=d1, requested_for_time_label="10:15 AM"))
        assert plan(c, provider_name="Tess Ortiz PT").status_code == 409
        _ok(plan(c, provider_name="Tess Ortiz PT", conflict_override=True))
        doc = await db.staff_tasks.find_one({"task_id": c}, {"_id": 0})
        ev = [e for e in doc["event_log"] if e["field"] == "details"][-1]
        rc = await db.receipts.find_one({"receipt_id": ev["receipt_id"]}, {"_id": 0})
        assert rc["result"] == "conflict_override" and set(rc["provider_refs"]) == {a, b}

        # same assignee double-booked across residents (no provider set)
        e1, e2 = ask(rids[0], "Stretching"), ask(rids[1], "Hand therapy")
        d2 = (date.fromisoformat(d1) + timedelta(days=1)).isoformat()
        for t in (e1, e2):
            _ok(requests.post(f"{API}/tasks/{t}/assign", headers=H["pt2"], json={"assigned_to": ids["pt2"]}, timeout=5))
        _ok(plan(e1, "pt2", requested_for_date=d2, requested_for_time_label="9:00 AM"))
        r = plan(e2, "pt2", requested_for_date=d2, requested_for_time_label="9:30 AM")
        assert r.status_code == 409 and r.json()["detail"]["conflicts"][0]["kind"] == "staff"
        assert "assigned to" in r.json()["detail"]["conflicts"][0]["shared"]
        _ok(plan(e2, "pt2", requested_for_date=d2, requested_for_time_label="1:00 PM"))

        # staff Upcoming shows both sides; the resident's own views never carry conflicts or other residents
        up = {i["task_id"]: i for i in _ok(requests.get(f"{API}/tasks/upcoming", headers=H["pt"],
                                                         params={"department": "therapy"}, timeout=5))["items"]}
        assert b in {x["task_id"] for x in up[a]["conflicts"]} and a in {x["task_id"] for x in up[b]["conflicts"]}
        ru = _ok(requests.get(f"{API}/tasks/resident-request/upcoming", params={"resident_id": rids[1]}, timeout=5))
        blob = repr(ru)
        assert "conflicts" not in blob and "Knee therapy" not in blob and rids[0] not in blob
        st = _ok(requests.get(f"{API}/tasks/resident-request/status", params={"resident_id": rids[1], "category": "therapy"}, timeout=5))
        assert "Knee therapy" not in repr(st)

        # recurrence: a generated occurrence carries the series provider and is checked like any request
        tpl = _ok(requests.post(f"{API}/tasks/templates", headers=H["admin"], json={
            "title": f"{TAG} weekly PT", "recur": "weekly", "weekday": date.fromisoformat(d1).weekday(),
            "time_label": "10:00 AM", "department": "therapy", "provider_name": "Tess Ortiz PT",
            "resident_id": rids[2]}, timeout=5))
        _ok(requests.post(f"{API}/tasks/spawn-today", headers=H["admin"], timeout=5))
        occ = await db.staff_tasks.find_one({"template_id": tpl["template_id"], "requested_for_date": d1}, {"_id": 0})
        assert occ and occ["provider_name"] == "Tess Ortiz PT"
        chk = _ok(requests.get(f"{API}/tasks/{occ['task_id']}/conflicts", headers=H["pt"], timeout=5))
        assert a in {x["task_id"] for x in chk["conflicts"]}
        # moving that one occurrence clear of the provider's other work leaves the series unchanged
        _ok(plan(occ["task_id"], requested_for_time_label="3:00 PM"))
        tdoc = await db.task_templates.find_one({"template_id": tpl["template_id"]}, {"_id": 0}) or \
            await db.staff_task_templates.find_one({"template_id": tpl["template_id"]}, {"_id": 0})
        assert tdoc["time_label"] == "10:00 AM"

        # a linked ride still follows an overridden reschedule and is not itself a staff conflict
        ride = _ok(requests.post(f"{API}/tasks/{a}/ride", headers=H["pt"], timeout=5))["task_id"]
        _ok(plan(a, requested_for_time_label="10:45 AM", conflict_override=True))
        assert (await db.staff_tasks.find_one({"task_id": ride}))["requested_for_time_label"] == "10:45 AM"
        chk = _ok(requests.get(f"{API}/tasks/{b}/conflicts", headers=H["pt"], timeout=5))
        assert ride not in {x["task_id"] for x in chk["conflicts"]}
    finally:
        await db.users.delete_many({"email": {"$regex": f"^{TAG}_"}})
        await db.residents.delete_many({"resident_id": {"$in": rids}})
        await db.departments.delete_many({"_tag": TAG})
        await db.staff_tasks.delete_many({"$or": [{"resident_id": {"$in": rids}}, {"title": {"$regex": f"^{TAG}"}}]})
        await db.task_templates.delete_many({"title": {"$regex": f"^{TAG}"}})
        await db.staff_task_templates.delete_many({"title": {"$regex": f"^{TAG}"}})


@pytest.mark.skipif(not _backend_up(), reason="backend not running")
def test_staff_double_booking_across_residents():
    asyncio.run(_run())
