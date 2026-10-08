"""RQ-023: re-cancelling a cancelled ride is answered truthfully, and the
status endpoint says when a ride shares a run. Over HTTP against a running
backend, own synthetic fixtures (2031 dates), cleaned up afterwards."""
import asyncio
import os
import sys
import uuid

import bcrypt
import pytest
import requests

BASE_URL = os.environ.get("TEST_API_BASE", os.environ.get("REACT_APP_BACKEND_URL", "http://127.0.0.1:8000")).rstrip("/")
API = f"{BASE_URL}/api"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TAG = f"rq23_{uuid.uuid4().hex[:8]}"
PW = "rq23-pw-12345678"
DAY = "2031-05-12"


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
    email = f"{TAG}_admin@example.com"
    await db.users.insert_one({
        "user_id": uid("user"), "email": email, "name": f"{TAG} admin", "role": "admin", "department": None,
        "auth_provider": "jwt", "created_at": now_utc().isoformat(),
        "password_hash": bcrypt.hashpw(PW.encode(), bcrypt.gensalt()).decode()})
    H = {"Authorization": f"Bearer {_ok(requests.post(f'{API}/auth/login', json={'email': email, 'password': PW}))['token']}"}
    rid = uid("res")
    await db.residents.insert_one({"resident_id": rid, "name": f"{TAG} Res", "room": f"{TAG}-1", "created_at": now_utc().isoformat()})
    ctx = {"resident_id": rid, "room": None, "conversation_session_id": None}
    try:
        for kind, body in (("drivers", {"name": f"{TAG} D"}), ("vehicles", {"name": f"{TAG} V", "capacity": 2})):
            _ok(requests.post(f"{API}/transportation/{kind}", headers=H, json=body))
        r = _ok(requests.post(f"{API}/transportation/request", json={
            "resident_id": rid, "purpose": "pharmacy", "requested_for_date": DAY, "start_time": "09:00",
            "source": "aria_voice"}))
        assert r["booked"] is True
        tid = r["task_id"]
        st = _ok(requests.get(f"{API}/transportation/request/status", params={"resident_id": rid}))
        assert st["run"]["shared"] is False
        run_id = (await db.staff_tasks.find_one({"task_id": tid}))["transport_run_id"]
        await db.transport_runs.update_one({"run_id": run_id}, {"$addToSet": {"resident_task_ids": "other_task"}})
        st = _ok(requests.get(f"{API}/transportation/request/status", params={"resident_id": rid}))
        assert st["run"]["shared"] is True

        first = _ok(requests.post(f"{API}/transportation/request/cancel-mine", json=ctx))
        assert not first.get("already_cancelled")
        again = _ok(requests.post(f"{API}/transportation/request/cancel-mine", json=ctx))
        assert again["already_cancelled"] is True and again["task_id"] == tid
        # No ride at all is still a 404.
        none = requests.post(f"{API}/transportation/request/cancel-mine",
                             json={"resident_id": "nobody_" + TAG, "room": None, "conversation_session_id": None})
        assert none.status_code == 404
    finally:
        tids = [t["task_id"] async for t in db.staff_tasks.find({"resident_id": rid}, {"task_id": 1})]
        await db.staff_tasks.delete_many({"resident_id": rid})
        await db.receipts.delete_many({"related_object_id": {"$in": tids}})
        await db.transport_runs.delete_many({"date": DAY, "resident_task_ids": {"$in": tids}})
        await db.transport_drivers.delete_many({"name": {"$regex": f"^{TAG}"}})
        await db.transport_vehicles.delete_many({"name": {"$regex": f"^{TAG}"}})
        await db.residents.delete_many({"resident_id": rid})
        await db.users.delete_many({"email": {"$regex": f"^{TAG}_"}})


def test_recancel_and_shared_flag():
    if not _backend_up():
        pytest.skip(f"backend not reachable at {BASE_URL}")
    asyncio.run(_run())
