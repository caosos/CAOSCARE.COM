"""careops-therapy-appointment-001: one non-recurring therapy appointment on the
canonical records (a StaffTask in the therapy department whose planned visit
window is requested_for_date / requested_for_time_label), end to end over HTTP.

- front desk creates it for a resident (resident-request bus, category therapy)
  -> it is the therapy department's work, not Administration's;
- the therapist (therapy staff) sets the window: PATCH /tasks/{id} ->
  `task_schedule_updated` receipt chained to the origin, `scheduled` history
  entry; the resident view (/tasks/resident-request/mine and /status) shows it
  and Aria's spoken status names the window;
- the front desk cannot set the window on a therapy task (403, nothing written);
- one reschedule -> a second `task_schedule_updated` receipt, before/after carry
  the window;
- attendance: start + complete -> `task_completed`; chain linked, one workflow id;
- a second appointment is cancelled with a reason: skip -> `task_cancelled`
  (status skipped) with the reason in history; the resident view no longer
  lists it as open.

    TEST_API_BASE=http://127.0.0.1:8070 pytest tests/test_therapy_appointment.py -q
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
TAG = f"thr_{uuid.uuid4().hex[:8]}"


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
    pw = "thr-pw-12345678"
    people = {"fd": ("front_desk", None), "pt": ("staff", "therapy"), "nurse": ("staff", "nursing")}
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
        day1 = (date.today() + timedelta(days=3)).isoformat()
        day2 = (date.today() + timedelta(days=4)).isoformat()

        # front desk enters the appointment for the resident, routed to Therapy
        t = _ok(requests.post(f"{API}/tasks/resident-request", headers=H["fd"], json={
            "category": "therapy", "resident_id": rid, "source": "front_desk",
            "summary": "Physical therapy session (knee)", "resident_words": "PT asked for a knee session next week"},
            timeout=5))
        tid = t["task_id"]
        doc = await db.staff_tasks.find_one({"task_id": tid}, {"_id": 0})
        assert doc["visibility_role"] == "therapy" and doc["category"] == "therapy" and doc["room"] == room
        # therapy staff see it; nursing staff do not
        assert any(x["task_id"] == tid for x in _ok(requests.get(f"{API}/tasks", headers=H["pt"], timeout=5)))
        assert not any(x["task_id"] == tid for x in _ok(requests.get(f"{API}/tasks", headers=H["nurse"], timeout=5)))

        # front desk cannot set the window on a therapy task
        r = requests.patch(f"{API}/tasks/{tid}", headers=H["fd"], json={"requested_for_date": day1, "requested_for_time_label": "10:00 AM"}, timeout=5)
        assert r.status_code == 403, r.text
        assert await db.receipts.count_documents({"related_object_id": tid}) == 1   # origin only

        # therapist plans the window
        _ok(requests.patch(f"{API}/tasks/{tid}", headers=H["pt"], json={"requested_for_date": day1, "requested_for_time_label": "10:00 AM"}, timeout=5))
        rec = await db.receipts.find_one({"related_object_id": tid, "action_type": "task_schedule_updated"}, {"_id": 0})
        assert rec and rec["after_state"]["requested_for_date"] == day1 and rec["before_state"]["requested_for_date"] is None
        assert rec["actor_id"] == ids["pt"] and rec["authority"] == "acts_for:therapy" and rec["identity_basis"] == "authenticated"
        doc = await db.staff_tasks.find_one({"task_id": tid}, {"_id": 0})
        sched = [e for e in doc["event_log"] if e["field"] == "scheduled"]
        assert len(sched) == 1 and day1 in sched[0]["text"] and "10:00 AM" in sched[0]["text"] and sched[0]["receipt_id"] == rec["receipt_id"]

        # resident sees the window (Home screen list + Aria status)
        mine = _ok(requests.get(f"{API}/tasks/resident-request/mine", params={"resident_id": rid}, timeout=5))
        item = next(x for x in (mine if isinstance(mine, list) else mine.get("requests", [])) if x["task_id"] == tid)
        assert item["scheduled_date"] == day1 and item["scheduled_time_label"] == "10:00 AM"
        s = _ok(requests.get(f"{API}/tasks/resident-request/status", params={"resident_id": rid, "category": "therapy"}, timeout=5))
        assert s["found"] and s["scheduled_date"] == day1 and "10:00 AM" in s["spoken"]

        # reschedule once
        _ok(requests.patch(f"{API}/tasks/{tid}", headers=H["pt"], json={"requested_for_date": day2, "requested_for_time_label": "2:00 PM"}, timeout=5))
        recs = [r async for r in db.receipts.find({"related_object_id": tid, "action_type": "task_schedule_updated"}, {"_id": 0}).sort("created_at", 1)]
        assert len(recs) == 2 and recs[1]["before_state"]["requested_for_date"] == day1 and recs[1]["after_state"]["requested_for_date"] == day2
        s = _ok(requests.get(f"{API}/tasks/resident-request/status", params={"resident_id": rid, "category": "therapy"}, timeout=5))
        assert s["scheduled_date"] == day2 and "2:00 PM" in s["spoken"] and "10:00 AM" not in s["spoken"]

        # attendance: therapist claims, starts, completes
        _ok(requests.post(f"{API}/tasks/{tid}/assign", headers=H["pt"], json={"assigned_to": ids["pt"]}, timeout=5))
        _ok(requests.post(f"{API}/tasks/{tid}/start", headers=H["pt"], timeout=5))
        _ok(requests.post(f"{API}/tasks/{tid}/complete", headers=H["pt"], json={"notes": "attended, 40 min, knee ROM improved"}, timeout=5))
        chain = [r async for r in db.receipts.find({"related_object_id": tid, "action_type": {"$not": {"$regex": "_refused$"}}}, {"_id": 0}).sort("created_at", 1)]
        kinds = [r["action_type"] for r in chain]
        assert kinds == ["resident_request_created", "task_schedule_updated", "task_schedule_updated", "task_assigned", "task_in_progress", "task_completed"], kinds
        for prev, cur in zip(chain, chain[1:]):
            assert cur["parent_receipt_id"] == prev["receipt_id"]
        assert {r["correlation_id"] for r in chain} == {chain[0]["receipt_id"]}
        hist = _ok(requests.get(f"{API}/tasks/resident-request/history", params={"resident_id": rid}, timeout=5))
        assert any(x["task_id"] == tid and f"taken care of by {names['pt']}" in x["spoken"] for x in hist["requests"])

        # second appointment, cancelled with a reason
        t2 = _ok(requests.post(f"{API}/tasks/resident-request", headers=H["fd"], json={
            "category": "therapy", "resident_id": rid, "source": "front_desk",
            "summary": "Occupational therapy follow-up", "resident_words": "OT follow-up requested"}, timeout=5))["task_id"]
        _ok(requests.patch(f"{API}/tasks/{t2}", headers=H["pt"], json={"requested_for_date": day2, "requested_for_time_label": "9:00 AM"}, timeout=5))
        _ok(requests.post(f"{API}/tasks/{t2}/skip", headers=H["pt"], json={"notes": "Cancelled: therapist out sick; family will rebook"}, timeout=5))
        d2 = await db.staff_tasks.find_one({"task_id": t2}, {"_id": 0})
        assert d2["status"] == "skipped"
        rec2 = await db.receipts.find_one({"related_object_id": t2, "action_type": "task_cancelled"}, {"_id": 0})
        assert rec2 and rec2["failure_reason"].startswith("Cancelled:") and rec2["before_state"]["status"] == "pending"
        assert any(e["field"] == "note" and e["text"].startswith("Cancelled:") for e in d2["event_log"])
        s = requests.get(f"{API}/tasks/resident-request/status", params={"resident_id": rid, "category": "therapy"}, timeout=5).json()
        assert not s.get("found")   # nothing open any more
    finally:
        await db.users.delete_many({"email": {"$regex": f"^{TAG}_"}})
        await db.staff_tasks.delete_many({"room": room})
        await db.receipts.delete_many({"room": room})
        await db.notifications.delete_many({"room": room})
        await db.residents.delete_one({"resident_id": rid})
        await db.departments.delete_many({"_tag": TAG})


@pytest.mark.skipif(not _backend_up(), reason="backend not reachable")
def test_therapy_appointment():
    assert os.environ.get("MONGO_URL") and os.environ.get("DB_NAME")
    asyncio.run(_run())
