"""careops-frontdesk-unified-inbox-inventory-001: the front desk "Needs
attention" view is the existing routing-exceptions read model, scoped by the
backend to what the front desk acts for (Administration). A front-desk
callback request that was not delivered is listed for the desk and can be
re-sent (receipted acts_for:administration); another department's request is
neither listed nor re-sendable (403); no delivery is claimed without a
provider. Uses the backend test gate's server.

    TEST_API_BASE=http://127.0.0.1:8131 pytest tests/test_front_desk_attention.py -q
"""
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
TAG = f"fda_{uuid.uuid4().hex[:8]}"


def _up():
    try:
        return requests.get(f"{API}/health", timeout=3).ok
    except Exception:
        return False


def _ok(r):
    assert r.status_code == 200, (r.status_code, r.text)
    return r.json()


async def _run():
    from motor.motor_asyncio import AsyncIOMotorClient
    from models import uid, now_utc
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    pw = "fda-pw-12345678"
    ids = {}
    for k, (role, dept) in {"fd": ("front_desk", None), "nurse": ("staff", "nursing"), "admin": ("admin", None)}.items():
        ids[k] = uid("user")
        await db.users.insert_one({"user_id": ids[k], "email": f"{TAG}_{k}@example.com", "name": f"{TAG} {k}", "role": role,
                                   "department": dept, "auth_provider": "jwt", "created_at": now_utc().isoformat(),
                                   "password_hash": bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()})
    rid = uid("res")
    await db.residents.insert_one({"resident_id": rid, "name": f"{TAG} Resident", "room": f"{TAG}-R", "created_at": now_utc().isoformat()})
    tids = []
    try:
        H = {k: {"Authorization": "Bearer " + requests.post(f"{API}/auth/login", json={"email": f"{TAG}_{k}@example.com", "password": pw}, timeout=5).json()["token"]} for k in ids}
        cb = _ok(requests.post(f"{API}/tasks/resident-request", headers=H["fd"], json={
            "category": "front_desk", "resident_id": rid, "source": "front_desk",
            "summary": "Callback about the September bill", "resident_words": "Please call me back about my bill"}, timeout=5))["task_id"]
        nur = _ok(requests.post(f"{API}/tasks/resident-request", json={
            "category": "nursing", "resident_id": rid, "room": f"{TAG}-R", "source": "aria_voice",
            "summary": "Need help to the bathroom"}, timeout=5))["task_id"]
        tids = [cb, nur]

        mine = {r["task_id"]: r for r in _ok(requests.get(f"{API}/ops/routing-exceptions", headers=H["fd"], timeout=5))["items"]}
        assert cb in mine and nur not in mine, set(mine)
        row = mine[cb]
        assert row["department"] == "administration" and "unassigned" in row["classes"]
        assert row["delivery"]["reached"] is False                       # no provider in the gate: not claimed as delivered

        before = await db.receipts.count_documents({"related_object_id": cb, "action_type": "department_renotified"})
        _ok(requests.post(f"{API}/ops/routing-exceptions/{cb}/renotify", headers=H["fd"], timeout=5))
        rs = await db.receipts.find({"related_object_id": cb, "action_type": "department_renotified"}).to_list(10)
        assert len(rs) == before + 1 and rs[-1]["authority"] == "acts_for:administration" and rs[-1]["actor_id"] == ids["fd"]
        assert await db.notifications.count_documents({"related_object_id": cb, "status": {"$in": ["sent", "delivered"]}}) == 0

        assert requests.post(f"{API}/ops/routing-exceptions/{nur}/renotify", headers=H["fd"], timeout=5).status_code in (403, 404)
        assert await db.receipts.count_documents({"related_object_id": nur, "action_type": "department_renotified"}) == 0
        assert requests.get(f"{API}/ops/routing-exceptions", timeout=5).status_code == 401
        allx = {r["task_id"] for r in _ok(requests.get(f"{API}/ops/routing-exceptions", headers=H["admin"], timeout=5))["items"]}
        assert {cb, nur} <= allx                                          # admin sees both
    finally:
        await db.users.delete_many({"email": {"$regex": f"^{TAG}_"}})
        await db.residents.delete_many({"resident_id": rid})
        await db.staff_tasks.delete_many({"task_id": {"$in": tids}})
        await db.receipts.delete_many({"related_object_id": {"$in": tids}})
        await db.notifications.delete_many({"related_object_id": {"$in": tids}})


def test_front_desk_needs_attention_is_scoped_and_actionable():
    if os.environ.get("DB_NAME") in ("caoscare", "", None):
        pytest.skip("point DB_NAME at a scratch database")
    if not _up():
        pytest.skip(f"backend not reachable at {API}")
    asyncio.new_event_loop().run_until_complete(_run())
