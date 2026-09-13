"""Activity log - read-only browser over the existing GET /receipts and
GET /events. No new write path; the new bits are extra optional query
params on /receipts (since/until/action_type/source/related_object_id/room)
that mirror what /events already accepts.

Own Motor client per asyncio.run() (co-runnable with the other DB tests).
Seeds a real receipt by creating+closing a task over HTTP, plus two
CaosEvent docs inserted directly. Cleans up.

    TEST_API_BASE=http://127.0.0.1:8001 pytest tests/test_activity_log.py -q
"""
import asyncio
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone

import bcrypt
import pytest
import requests

BASE_URL = os.environ.get("TEST_API_BASE", os.environ.get("REACT_APP_BACKEND_URL", "http://127.0.0.1:8000")).rstrip("/")
API = f"{BASE_URL}/api"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

TAG = f"act_{uuid.uuid4().hex[:8]}"
CONV = f"{TAG}-conv"
ROOM = f"{TAG}-201"


def _backend_up():
    try:
        requests.get(f"{BASE_URL}/api/health", timeout=3).raise_for_status()
        return True
    except Exception:
        return False


def _login(email, pw):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": pw}, timeout=5)
    r.raise_for_status()
    return {"Authorization": f"Bearer {r.json()['token']}"}


async def _run():
    from motor.motor_asyncio import AsyncIOMotorClient
    from models import uid, now_utc
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]

    now = datetime.now(timezone.utc)
    pw = "act-pw-12345678"
    admin_id, staff_id = uid("user"), uid("user")
    admin_email, staff_email = f"{TAG}_admin@example.com", f"{TAG}_staff@example.com"
    for uid_, email, role in ((admin_id, admin_email, "admin"), (staff_id, staff_email, "staff")):
        await db.users.insert_one({
            "user_id": uid_, "email": email, "name": f"{TAG} {role}", "role": role,
            "department": "maintenance" if role == "staff" else None, "auth_provider": "jwt",
            "password_hash": bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode(),
            "created_at": now_utc().isoformat(),
        })

    ev1 = {"event_id": uid("evt"), "event_type": "admin_aria.message", "source": "admin_aria",
           "actor_id": admin_id, "actor_role": "admin", "resident_id": f"{TAG}-res",
           "conversation_id": CONV, "created_at": now.isoformat(),
           "metadata": {"message": f"{TAG} what's overdue in maintenance?"}}
    ev2 = {"event_id": uid("evt"), "event_type": "device.command", "source": "device",
           "conversation_id": CONV, "status": "command_verified", "target_type": "device",
           "target_id": f"{TAG}-dev", "duration_ms": 812.0,
           "created_at": (now + timedelta(seconds=2)).isoformat(), "metadata": {}}
    await db.events.insert_many([ev1, ev2])

    try:
        A = _login(admin_email, pw)
        S = _login(staff_email, pw)

        # a real receipt: create + close a task over HTTP
        r = requests.post(f"{API}/tasks", headers=A, json={
            "title": f"{TAG} fix light", "description": f"{TAG} fix light",
            "category": "maintenance", "visibility_role": "maintenance", "room": ROOM,
        }, timeout=5)
        assert r.status_code == 200, r.text
        task_id = r.json()["task_id"]
        requests.post(f"{API}/tasks/{task_id}/start", headers=A, timeout=5)
        requests.post(f"{API}/tasks/{task_id}/complete", headers=A, json={"notes": f"{TAG} done"}, timeout=5)

        # ---- RECEIPTS ----
        assert requests.get(f"{API}/receipts", headers=S, timeout=5).status_code == 403

        mine = requests.get(f"{API}/receipts", headers=A, params={"related_object_id": task_id}, timeout=5).json()
        assert mine and all(x["related_object_id"] == task_id for x in mine)
        rc = mine[0]
        assert rc["action_type"] == "task_created" and rc["source"] == "staff"
        # the lifecycle mutates that receipt's status in place
        assert rc["status"] == "completed"

        one = requests.get(f"{API}/receipts/{rc['receipt_id']}", headers=A, timeout=5)
        assert one.status_code == 200 and one.json()["receipt_id"] == rc["receipt_id"]

        def rc_q(**p):
            return {x["receipt_id"] for x in requests.get(f"{API}/receipts", headers=A, params={**p, "limit": 1000}, timeout=8).json()}

        assert rc["receipt_id"] in rc_q(related_object_type="task")
        assert rc["receipt_id"] in rc_q(action_type="task_created")
        assert rc["receipt_id"] in rc_q(source="staff", room=ROOM)
        assert rc["receipt_id"] in rc_q(status="completed", related_object_id=task_id)
        # new since/until params (mirror /events)
        assert rc["receipt_id"] in rc_q(since=(now - timedelta(days=1)).isoformat(), until=(now + timedelta(days=1)).isoformat())
        assert rc["receipt_id"] not in rc_q(since=(now + timedelta(days=1)).isoformat())
        assert rc["receipt_id"] not in rc_q(action_type="does_not_exist")

        # ---- EVENTS ----
        assert requests.get(f"{API}/events", headers=S, timeout=5).status_code == 403

        def ev_q(**p):
            return {x["event_id"] for x in requests.get(f"{API}/events", headers=A, params={**p, "limit": 2000}, timeout=8).json()}

        both = {ev1["event_id"], ev2["event_id"]}
        assert both.issubset(ev_q(conversation_id=CONV))
        assert ev1["event_id"] in ev_q(event_type="admin_aria.message")
        assert ev1["event_id"] in ev_q(resident_id=f"{TAG}-res")
        assert both.issubset(ev_q(since=(now - timedelta(minutes=5)).isoformat(), until=(now + timedelta(minutes=5)).isoformat()))

        thread = requests.get(f"{API}/events/conversation/{CONV}", headers=A, timeout=5).json()
        got = [e["event_id"] for e in thread if e["event_id"] in both]
        assert got == [ev1["event_id"], ev2["event_id"]], got  # chronological
    finally:
        tids = [t["task_id"] for t in await db.staff_tasks.find({"room": {"$regex": f"^{TAG}"}}, {"_id": 0, "task_id": 1}).to_list(50)]
        await db.staff_tasks.delete_many({"room": {"$regex": f"^{TAG}"}})
        if tids:
            await db.receipts.delete_many({"related_object_id": {"$in": tids}})
        await db.receipts.delete_many({"room": {"$regex": f"^{TAG}"}})
        await db.events.delete_many({"event_id": {"$in": [ev1["event_id"], ev2["event_id"]]}})
        await db.users.delete_many({"email": {"$regex": f"^{TAG}_"}})


def test_activity_log():
    if not _backend_up():
        pytest.skip(f"backend not reachable at {BASE_URL}")
    asyncio.run(_run())
