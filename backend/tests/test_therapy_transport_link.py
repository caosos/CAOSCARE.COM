"""careops-therapy-transport-link-001: a planned therapy appointment can need a
ride; "ride needed" creates or attaches EXACTLY ONE ordinary transportation
request through the shared core, linked both ways with receipts, and the
appointment's reschedule / cancel flow to it.

    TEST_API_BASE=http://127.0.0.1:8070 pytest tests/test_therapy_transport_link.py -q
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
TAG = f"trl_{uuid.uuid4().hex[:8]}"


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
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    pw = "trl-pw-12345678"
    people = {"fd": ("front_desk", None), "pt": ("staff", "therapy"), "nurse": ("staff", "nursing"), "drv": ("staff", "transportation"), "hk": ("staff", "housekeeping")}
    ids, names = {}, {}
    for k, (role, dept) in people.items():
        ids[k], names[k] = uid("user"), f"{TAG} {k}"
        await db.users.insert_one({
            "user_id": ids[k], "email": f"{TAG}_{k}@example.com", "name": names[k], "role": role,
            "department": dept, "auth_provider": "jwt", "created_at": now_utc().isoformat(),
            "password_hash": bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode(),
        })
    if not await db.departments.find_one({"slug": "therapy"}):
        await db.departments.insert_one({"department_id": uid("dept"), "slug": "therapy", "label": "Therapy",
                                         "active": True, "created_at": now_utc().isoformat(), "_tag": TAG})
    room = f"{TAG}-R"
    rid = uid("res")
    await db.residents.insert_one({"resident_id": rid, "name": f"{TAG} Resident", "preferred_name": "Pat", "room": room,
                                   "created_at": now_utc().isoformat()})
    try:
        H = {k: _login(f"{TAG}_{k}@example.com", pw) for k in people}
        d1 = (date.today() + timedelta(days=3)).isoformat()
        d2 = (date.today() + timedelta(days=5)).isoformat()
        appt = _ok(requests.post(f"{API}/tasks/resident-request", headers=H["fd"], json={
            "category": "therapy", "resident_id": rid, "source": "front_desk",
            "summary": "Physical therapy (knee)", "resident_words": "knee session"}, timeout=5))["task_id"]

        # unplanned -> 422, nothing created
        r = requests.post(f"{API}/tasks/{appt}/ride", headers=H["pt"], timeout=5)
        assert r.status_code == 422, r.text
        assert await db.staff_tasks.count_documents({"category": "transportation", "resident_id": rid}) == 0

        _ok(requests.patch(f"{API}/tasks/{appt}", headers=H["pt"], json={"requested_for_date": d1, "requested_for_time_label": "10:00 AM"}, timeout=5))

        # nursing staff cannot ask for the ride (403, nothing created)
        r = requests.post(f"{API}/tasks/{appt}/ride", headers=H["nurse"], timeout=5)
        assert r.status_code == 403, r.text
        assert await db.staff_tasks.count_documents({"category": "transportation", "resident_id": rid}) == 0

        # therapist: ride needed -> exactly one transportation request, linked both ways, receipted
        res = _ok(requests.post(f"{API}/tasks/{appt}/ride", headers=H["pt"], timeout=5))
        ride = res["task_id"]
        assert res["already_linked"] is False and res["attached_existing"] is False
        rdoc = await db.staff_tasks.find_one({"task_id": ride}, {"_id": 0})
        assert rdoc["category"] == "transportation" and rdoc["visibility_role"] == "transportation"
        assert rdoc["resident_id"] == rid and rdoc["room"] == room
        assert rdoc["requested_for_date"] == d1 and rdoc["requested_for_time_label"] == "10:00 AM"
        assert rdoc["linked_appointment_task_id"] == appt and "Physical therapy (knee)" in rdoc["description"]
        adoc = await db.staff_tasks.find_one({"task_id": appt}, {"_id": 0})
        assert adoc["linked_ride_task_id"] == ride
        link = await db.receipts.find_one({"related_object_id": appt, "action_type": "task_ride_requested"}, {"_id": 0})
        assert link and ride in link["provider_refs"] and link["actor_id"] == ids["pt"] and link["authority"] == "acts_for:therapy"
        origin = await db.receipts.find_one({"related_object_id": ride, "action_type": "transportation_requested"}, {"_id": 0})
        assert origin and origin["receipt_id"] in link["provider_refs"] and origin["actor_id"] == ids["pt"]
        assert any(e["field"] == "ride_requested" and e["receipt_id"] == link["receipt_id"] for e in adoc["event_log"])
        assert any(e["field"] == "linked_appointment" and e["receipt_id"] == link["receipt_id"] for e in rdoc["event_log"])
        assert await db.staff_tasks.count_documents({"category": "transportation", "resident_id": rid}) == 1
        # visible to transportation staff; linked view readable by the therapist, not by nursing
        assert any(t["task_id"] == ride for t in _ok(requests.get(f"{API}/tasks", headers=H["drv"], timeout=5)))
        v = _ok(requests.get(f"{API}/tasks/{appt}/ride", headers=H["pt"], timeout=5))
        assert v["linked"] and v["ride"]["task_id"] == ride and v["ride"]["requested_for_date"] == d1
        assert requests.get(f"{API}/tasks/{appt}/ride", headers=H["nurse"], timeout=5).status_code == 403
        # resident's ride status sees it
        st = _ok(requests.get(f"{API}/transportation/request/status", params={"resident_id": rid}, timeout=5))
        assert st["found"] and st["requested_for_date"] == d1

        # idempotent: asking again returns the same ride, no second one
        res2 = _ok(requests.post(f"{API}/tasks/{appt}/ride", headers=H["pt"], timeout=5))
        assert res2["task_id"] == ride and res2["already_linked"] is True
        assert await db.staff_tasks.count_documents({"category": "transportation", "resident_id": rid}) == 1
        assert await db.receipts.count_documents({"related_object_id": appt, "action_type": "task_ride_requested"}) == 1

        # reschedule the appointment -> the ride follows (its own change receipt)
        _ok(requests.patch(f"{API}/tasks/{appt}", headers=H["pt"], json={"requested_for_date": d2, "requested_for_time_label": "2:00 PM"}, timeout=5))
        rdoc = await db.staff_tasks.find_one({"task_id": ride}, {"_id": 0})
        assert rdoc["requested_for_date"] == d2 and rdoc["requested_for_time_label"] == "2:00 PM"
        ch = await db.receipts.find_one({"related_object_id": ride, "action_type": "transportation_changed"}, {"_id": 0})
        assert ch and ch["before_state"]["requested_for_date"] == d1 and ch["after_state"]["requested_for_date"] == d2
        assert ch["actor_id"] == ids["pt"]
        # a note-only PATCH does not touch the ride
        n_before = await db.receipts.count_documents({"related_object_id": ride})
        _ok(requests.patch(f"{API}/tasks/{appt}", headers=H["pt"], json={"notes": "bring the walker"}, timeout=5))
        assert await db.receipts.count_documents({"related_object_id": ride}) == n_before

        # cancel the appointment -> the ride is cancelled with the reason
        _ok(requests.post(f"{API}/tasks/{appt}/skip", headers=H["pt"], json={"notes": "therapist out sick"}, timeout=5))
        rdoc = await db.staff_tasks.find_one({"task_id": ride}, {"_id": 0})
        assert rdoc["status"] == "skipped" and rdoc["notes"].startswith("Appointment cancelled: therapist out sick")
        cx = await db.receipts.find_one({"related_object_id": ride, "action_type": "transportation_cancelled"}, {"_id": 0})
        assert cx and "therapist out sick" in (cx.get("result") or "")
        st = _ok(requests.get(f"{API}/transportation/request/status", params={"resident_id": rid}, timeout=5))
        assert st["found"] and st["status"] == "skipped" and not st["booked"]
        v = _ok(requests.get(f"{API}/tasks/{appt}/ride", headers=H["pt"], timeout=5))
        assert v["ride"]["status"] == "skipped" and "therapist out sick" in v["ride"]["cancel_reason"]

        # a second planned appointment on a date with an existing open ride attaches to it (no duplicate)
        appt2 = _ok(requests.post(f"{API}/tasks/resident-request", headers=H["fd"], json={
            "category": "therapy", "resident_id": rid, "source": "front_desk",
            "summary": "OT follow-up", "resident_words": "OT follow-up"}, timeout=5))["task_id"]
        _ok(requests.patch(f"{API}/tasks/{appt2}", headers=H["pt"], json={"requested_for_date": d2, "requested_for_time_label": "9:00 AM"}, timeout=5))
        other = _ok(requests.post(f"{API}/transportation/staff/request", headers=H["fd"], json={
            "resident_id": rid, "purpose": "pharmacy", "requested_for_date": d2, "requested_for_time_label": "8:30 AM"}, timeout=5))["task_id"]
        res3 = _ok(requests.post(f"{API}/tasks/{appt2}/ride", headers=H["pt"], timeout=5))
        assert res3["task_id"] == other and res3["attached_existing"] is True
        assert await db.staff_tasks.count_documents({"category": "transportation", "resident_id": rid, "status": {"$in": ["pending", "in_progress"]}}) == 1
        a2 = await db.staff_tasks.find_one({"task_id": appt2}, {"_id": 0})
        assert a2["linked_ride_task_id"] == other
        # completing the appointment leaves the ride alone
        _ok(requests.post(f"{API}/tasks/{appt2}/complete", headers=H["pt"], json={"notes": "attended"}, timeout=5))
        assert (await db.staff_tasks.find_one({"task_id": other}, {"_id": 0}))["status"] == "pending"
        # in-room work (housekeeping) never gets a ride: 422, nothing created
        hk = _ok(requests.post(f"{API}/tasks/resident-request", headers=H["fd"], json={
            "category": "housekeeping", "resident_id": rid, "source": "front_desk",
            "summary": "Deep clean", "resident_words": "deep clean"}, timeout=5))["task_id"]
        _ok(requests.patch(f"{API}/tasks/{hk}", headers=H["hk"], json={"requested_for_date": d1, "requested_for_time_label": "2:00 PM"}, timeout=5))
        rides_before = await db.staff_tasks.count_documents({"category": "transportation", "resident_id": rid})
        r = requests.post(f"{API}/tasks/{hk}/ride", headers=H["hk"], timeout=5)
        assert r.status_code == 422 and "room" in r.text, r.text
        assert await db.staff_tasks.count_documents({"category": "transportation", "resident_id": rid}) == rides_before
    finally:
        await db.users.delete_many({"email": {"$regex": f"^{TAG}_"}})
        await db.staff_tasks.delete_many({"room": room})
        await db.receipts.delete_many({"room": room})
        await db.notifications.delete_many({"room": room})
        await db.residents.delete_one({"resident_id": rid})
        await db.departments.delete_many({"_tag": TAG})


@pytest.mark.skipif(not _backend_up(), reason="backend not reachable")
def test_therapy_transport_link():
    assert os.environ.get("MONGO_URL") and os.environ.get("DB_NAME")
    asyncio.run(_run())
