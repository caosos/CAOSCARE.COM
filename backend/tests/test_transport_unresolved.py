"""careops-transport-unresolved-001: the Transportation "Unresolved" count equals the canonical open,
unbooked ride requests; each row carries who/what/when/owner/state/next action; access is transport
coordinators only.

    TEST_API_BASE=http://127.0.0.1:8070 pytest tests/test_transport_unresolved.py -q
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
TAG = f"tun_{uuid.uuid4().hex[:8]}"


def _backend_up() -> bool:
    try:
        requests.get(f"{API}/health", timeout=3).raise_for_status()
        return True
    except Exception:
        return False


def _ok(r):
    assert r.status_code == 200, (r.status_code, r.text)
    return r.json()


async def _run():
    from motor.motor_asyncio import AsyncIOMotorClient
    from models import uid, now_utc
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    pw = "tun-pw-12345678"
    ids = {}
    for k, (role, dept) in {"fd": ("front_desk", None), "driver": ("staff", "transportation"), "nurse": ("staff", "nursing"), "admin": ("admin", None)}.items():
        ids[k] = uid("user")
        await db.users.insert_one({"user_id": ids[k], "email": f"{TAG}_{k}@example.com", "name": f"{TAG} {k}", "role": role,
                                   "department": dept, "auth_provider": "jwt", "created_at": now_utc().isoformat(),
                                   "password_hash": bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()})
    rid = uid("res")
    await db.residents.insert_one({"resident_id": rid, "name": f"{TAG} Resident", "room": f"{TAG}-R", "created_at": now_utc().isoformat()})
    d1 = (date.today() + timedelta(days=2)).isoformat()
    try:
        tok = lambda k: {"Authorization": "Bearer " + requests.post(f"{API}/auth/login", json={"email": f"{TAG}_{k}@example.com", "password": pw}, timeout=5).json()["token"]}
        H = {k: tok(k) for k in ids}
        ride = lambda purpose, dte, label: _ok(requests.post(f"{API}/transportation/staff/request", headers=H["fd"], json={
            "resident_id": rid, "purpose": purpose, "requested_for_date": dte, "requested_for_time_label": label}, timeout=5))
        a = ride("Dentist on Main St", d1, "around 10")
        a_id = a.get("task_id") or a["request"]["task_id"]
        await db.staff_tasks.update_one({"task_id": a_id}, {"$set": {"re_request_count": 1}})        # asked twice
        b = ride("Eye doctor", (date.today() + timedelta(days=3)).isoformat(), "afternoon")
        b_id = b.get("task_id") or b["request"]["task_id"]
        rep = _ok(requests.get(f"{API}/transportation/report", headers=H["admin"], timeout=5))
        rows = rep["current_state"]["waiting_unbooked"]
        mine = {r["task_id"]: r for r in rows if r["resident_name"] == f"{TAG} Resident"}
        assert set(mine) == {a_id, b_id}
        # the count is exactly the list, and the list is exactly the canonical records
        assert rep["summary"]["total_unresolved"] == len(rows)
        canon = await db.staff_tasks.count_documents({"category": "transportation", "status": {"$in": ["pending", "in_progress"]},
                                                      "transport_run_id": {"$in": [None, ""]}, "transport_slot_id": {"$in": [None, ""]}})
        assert canon == len(rows)
        assert "any date" in rep["summary"]["unresolved_scope"]
        ra = mine[a_id]
        assert ra["purpose"].startswith("Dentist") and ra["requested_for_date"] == d1 and ra["requested_for_time_label"] == "around 10"
        assert ra["times_asked"] == 2 and "asked 2 times" in ra["next_action"] and ra["booked"] is False and ra["status"] == "pending"
        assert mine[b_id]["next_action"].startswith("Book a pickup") and mine[b_id]["owner"] is None and mine[b_id]["currency"]["bucket"] == "current"
        assert a_id in {r["task_id"] for r in rep["current_state"]["follow_ups_required"]}
        # access: transport coordinators only
        for k in ("fd", "driver"):
            assert requests.get(f"{API}/transportation/report", headers=H[k], timeout=5).status_code == 200, k
        assert requests.get(f"{API}/transportation/report", headers=H["nurse"], timeout=5).status_code == 403
        assert requests.get(f"{API}/transportation/report", timeout=5).status_code == 401
        # a row's record opens with its receipt trail (the detail the UI's Open uses)
        d = _ok(requests.get(f"{API}/tasks/{a_id}/detail", headers=H["fd"], timeout=5))
        assert d["task"]["task_id"] == a_id and d["receipts"][0]["action_type"] == "transportation_requested"
    finally:
        await db.users.delete_many({"email": {"$regex": f"^{TAG}_"}})
        await db.residents.delete_many({"resident_id": rid})
        tids = [x["task_id"] for x in await db.staff_tasks.find({"resident_id": rid}, {"task_id": 1}).to_list(20)]
        await db.staff_tasks.delete_many({"task_id": {"$in": tids}})
        await db.receipts.delete_many({"related_object_id": {"$in": tids}})
        await db.notifications.delete_many({"related_object_id": {"$in": tids}})


@pytest.mark.skipif(not _backend_up(), reason="backend not running")
def test_unresolved_count_equals_canonical_rows_and_access_is_scoped():
    asyncio.run(_run())
