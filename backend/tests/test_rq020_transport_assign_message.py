"""RQ-020: when staff assign a ride and nothing is free, the refusal reads
as a sentence (it used to say "No a free driver and vehicle for ...").

Over HTTP against a running backend, own synthetic fixtures:
    TEST_API_BASE=http://127.0.0.1:8070 pytest tests/test_rq020_transport_assign_message.py -q
"""
import asyncio
import os
import sys
import uuid

import bcrypt
import requests

BASE_URL = os.environ.get("TEST_API_BASE", os.environ.get("REACT_APP_BACKEND_URL", "http://127.0.0.1:8000")).rstrip("/")
API = f"{BASE_URL}/api"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

TAG = f"rq020_{uuid.uuid4().hex[:8]}"
PW = "rq020-pw-12345678"
from datetime import date as _date, timedelta as _td
SATURDAY = (_date.today() + _td(days=((5 - _date.today().weekday()) % 7) + 7)).isoformat()


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
    token = _ok(requests.post(f"{API}/auth/login", json={"email": email, "password": PW}, timeout=10))["token"]
    H = {"Authorization": f"Bearer {token}"}
    rid = uid("res")
    await db.residents.insert_one({"resident_id": rid, "name": f"{TAG} Resident", "room": TAG,
                                   "created_at": now_utc().isoformat()})
    driver_id = vehicle_id = None
    try:
        # A weekday-only driver and a van: nothing can run on a Saturday.
        driver_id = _ok(requests.post(f"{API}/transportation/drivers", headers=H, timeout=10, json={
            "name": f"{TAG} Driver", "work_days": [0, 1, 2, 3, 4]}))["driver_id"]
        vehicle_id = _ok(requests.post(f"{API}/transportation/vehicles", headers=H, timeout=10,
                                       json={"name": f"{TAG} Van", "capacity": 2}))["vehicle_id"]
        ride = _ok(requests.post(f"{API}/transportation/request", timeout=10, json={
            "resident_id": rid, "purpose": "church", "requested_for_date": SATURDAY, "source": "aria_voice"}))
        assert ride["booked"] is False
        url = f"{API}/transportation/request/{ride['task_id']}/assign"
        free = _ok(requests.post(url, headers=H, timeout=10, json={"start_time": "09:00"}))
        assert free["booked"] is False and free["reason"] == "no_availability"
        assert free["message"].startswith("No free driver and vehicle is available for 09:00 on "), free["message"]
        named = _ok(requests.post(url, headers=H, timeout=10, json={
            "start_time": "09:00", "driver_id": driver_id}))
        assert named["booked"] is False
        assert named["message"].startswith("The chosen driver/vehicle is not available for 09:00 on "), named["message"]
    finally:
        await db.staff_tasks.delete_many({"resident_id": rid})
        await db.receipts.delete_many({"resident_id": rid})
        await db.residents.delete_one({"resident_id": rid})
        await db.transport_drivers.delete_many({"name": {"$regex": f"^{TAG}"}})
        await db.transport_vehicles.delete_many({"name": {"$regex": f"^{TAG}"}})
        await db.users.delete_many({"email": {"$regex": f"^{TAG}_"}})


def test_unavailable_assignment_message_reads_correctly():
    try:
        requests.get(f"{API}/health", timeout=3).raise_for_status()
    except Exception:
        import pytest
        pytest.skip("backend not running")
    asyncio.run(_run())
