"""careops-transport-new-order-001: the admin Transportation screen's New ride uses the one canonical
staff ride path. An admin creates exactly one ride request with an origin receipt, it shows in the
report's unresolved list and the calendar's pending rides; a nurse is refused and nothing is written;
an anonymous caller gets 401.

    TEST_API_BASE=http://127.0.0.1:8070 pytest tests/test_transport_new_ride_entry.py -q
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
TAG = f"tnr_{uuid.uuid4().hex[:8]}"


def _backend_up() -> bool:
    try:
        requests.get(f"{API}/health", timeout=3).raise_for_status()
        return True
    except Exception:
        return False


async def _run():
    from motor.motor_asyncio import AsyncIOMotorClient
    from models import uid, now_utc
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    pw = "tnr-pw-12345678"
    ids = {}
    for k, (role, dept) in {"admin": ("admin", None), "nurse": ("staff", "nursing")}.items():
        ids[k] = uid("user")
        await db.users.insert_one({"user_id": ids[k], "email": f"{TAG}_{k}@example.com", "name": f"{TAG} {k}", "role": role,
                                   "department": dept, "auth_provider": "jwt", "created_at": now_utc().isoformat(),
                                   "password_hash": bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()})
    rid = uid("res")
    await db.residents.insert_one({"resident_id": rid, "name": f"{TAG} Resident", "room": f"{TAG}-R", "created_at": now_utc().isoformat()})
    day = (date.today() + timedelta(days=2)).isoformat()
    body = {"resident_id": rid, "purpose": f"{TAG} dentist", "requested_for_date": day, "requested_for_time_label": "around 10"}
    try:
        tok = lambda k: {"Authorization": "Bearer " + requests.post(f"{API}/auth/login", json={"email": f"{TAG}_{k}@example.com", "password": pw}, timeout=5).json()["token"]}
        H = {k: tok(k) for k in ids}

        assert requests.post(f"{API}/transportation/staff/request", json=body, timeout=5).status_code == 401
        assert requests.post(f"{API}/transportation/staff/request", headers=H["nurse"], json=body, timeout=5).status_code == 403
        assert await db.staff_tasks.count_documents({"resident_id": rid}) == 0          # refusal wrote nothing

        r = requests.post(f"{API}/transportation/staff/request", headers=H["admin"], json=body, timeout=5)
        assert r.status_code == 200, r.text
        data = r.json()
        tid = data.get("task_id") or data["request"]["task_id"]
        tasks = await db.staff_tasks.find({"resident_id": rid}, {"_id": 0}).to_list(10)
        assert len(tasks) == 1 and tasks[0]["task_id"] == tid and tasks[0]["category"] == "transportation"
        origin = await db.receipts.find_one({"related_object_id": tid, "action_type": "transportation_requested"}, {"_id": 0})
        assert origin and origin.get("requested_by") == ids["admin"]

        rep = requests.get(f"{API}/transportation/report", headers=H["admin"], timeout=5).json()
        assert tid in [x["task_id"] for x in rep["current_state"]["waiting_unbooked"]]
        cal = requests.get(f"{API}/transportation/calendar", headers=H["admin"], params={"date": day}, timeout=5).json()
        pending = [p["task_id"] for d in cal["days"] for p in d.get("pending", [])]
        assert tid in pending
    finally:
        tids = [t["task_id"] async for t in db.staff_tasks.find({"resident_id": rid}, {"task_id": 1})]
        await db.users.delete_many({"email": {"$regex": f"^{TAG}_"}})
        await db.residents.delete_many({"resident_id": rid})
        await db.staff_tasks.delete_many({"task_id": {"$in": tids}})
        await db.receipts.delete_many({"related_object_id": {"$in": tids}})
        await db.notifications.delete_many({"related_object_id": {"$in": tids}})


@pytest.mark.skipif(not _backend_up(), reason="backend not running")
def test_admin_new_ride_is_one_canonical_request_and_nurse_is_refused():
    asyncio.run(_run())
