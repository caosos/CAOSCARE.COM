"""Maintenance work-order workflow on the existing StaffTask spine.

A work order == a StaffTask with visibility_role == "maintenance". Proves:
department isolation, admin + department-lead creation, claim/start/
complete by a technician, completion persistence + receipt trail, no
regression to department routing, and that the Operations Overview reads
the same StaffTask truth (no duplicate model).

Own Motor client per asyncio.run() so this stays co-runnable with the
other DB test files. Seeds TAG-prefixed users/tasks, deletes them after.

    TEST_API_BASE=http://127.0.0.1:8001 pytest tests/test_maintenance_workorders.py -q
Defaults to http://127.0.0.1:8000. Skips cleanly if unreachable.
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

TAG = f"mwo_{uuid.uuid4().hex[:8]}"
ROOM = f"{TAG}-101"
ROOM2 = f"{TAG}-102"
HK_ROOM = f"{TAG}-HK"


def _backend_up() -> bool:
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

    pw = "wo-pw-12345678"
    users = {
        "admin": {"role": "admin", "department": None},
        "tech1": {"role": "staff", "department": "maintenance"},
        "tech2": {"role": "staff", "department": "maintenance"},
        "hk": {"role": "staff", "department": "housekeeping"},
    }
    for k, u in users.items():
        u["user_id"] = uid("user")
        u["email"] = f"{TAG}_{k}@example.com"
        await db.users.insert_one({
            "user_id": u["user_id"], "email": u["email"], "name": f"{TAG} {k}",
            "role": u["role"], "department": u["department"], "auth_provider": "jwt",
            "password_hash": bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode(),
            "created_at": now_utc().isoformat(),
        })

    try:
        A = _login(users["admin"]["email"], pw)
        T1 = _login(users["tech1"]["email"], pw)
        T2 = _login(users["tech2"]["email"], pw)
        HK = _login(users["hk"]["email"], pw)

        # --- admin creates two maintenance work orders ---
        r = requests.post(f"{API}/tasks", headers=A, json={
            "title": f"{TAG} leaking faucet", "description": f"{TAG} leaking faucet", "category": "maintenance",
            "visibility_role": "maintenance", "room": ROOM, "priority": "high",
        }, timeout=5)
        assert r.status_code == 200, r.text
        wo1 = r.json()["task_id"]
        assert r.json()["visibility_role"] == "maintenance"

        r = requests.post(f"{API}/tasks", headers=A, json={
            "title": f"{TAG} flickering hallway light", "description": f"{TAG} flickering hallway light", "category": "maintenance",
            "visibility_role": "maintenance", "room": ROOM2, "priority": "normal",
        }, timeout=5)
        wo2 = r.json()["task_id"]

        # --- department isolation: housekeeping does NOT see maintenance WOs ---
        hk_tasks = requests.get(f"{API}/tasks", headers=HK, timeout=5).json()
        assert not any(t["task_id"] in (wo1, wo2) for t in hk_tasks), "housekeeping saw maintenance work"

        # --- tech1 (maintenance staff) DOES see them ---
        t1_tasks = requests.get(f"{API}/tasks", headers=T1, timeout=5).json()
        assert {wo1, wo2}.issubset({t["task_id"] for t in t1_tasks})

        # --- a maintenance lead can raise a work order without an admin,
        #     and it is forced to their own department even if they try
        #     to aim it elsewhere ---
        r = requests.post(f"{API}/tasks", headers=T1, json={
            "title": f"{TAG} broken door closer", "description": f"{TAG} broken door closer", "category": "housekeeping",
            "visibility_role": "housekeeping", "room": ROOM,
        }, timeout=5)
        assert r.status_code == 200, r.text
        wo3 = r.json()["task_id"]
        assert r.json()["visibility_role"] == "maintenance" and r.json()["category"] == "maintenance"

        # housekeeping staff creating -> forced to housekeeping, invisible to tech1
        r = requests.post(f"{API}/tasks", headers=HK, json={
            "title": f"{TAG} deep clean 102", "description": f"{TAG} deep clean 102", "category": "maintenance", "visibility_role": "maintenance",
            "room": HK_ROOM,
        }, timeout=5)
        assert r.status_code == 200 and r.json()["visibility_role"] == "housekeeping", r.text
        hk_wo = r.json()["task_id"]
        assert hk_wo not in {t["task_id"] for t in requests.get(f"{API}/tasks", headers=T1, timeout=5).json()}

        # --- claim -> start -> complete by tech1 ---
        r = requests.post(f"{API}/tasks/{wo1}/assign", headers=T1, json={"assigned_to": users["tech1"]["user_id"]}, timeout=5)
        assert r.status_code == 200 and r.json()["assigned_to"] == users["tech1"]["user_id"]
        assert r.json()["assigned_name"] == f"{TAG} tech1"

        r = requests.post(f"{API}/tasks/{wo1}/start", headers=T1, timeout=5)
        assert r.status_code == 200 and r.json()["status"] == "in_progress" and r.json()["started_at"]

        r = requests.post(f"{API}/tasks/{wo1}/complete", headers=T1, json={"notes": f"{TAG} replaced washer, no more drip"}, timeout=5)
        assert r.status_code == 200 and r.json()["status"] == "completed"
        assert r.json()["completed_by_name"] == f"{TAG} tech1"

        # --- completion + history persists ---
        detail = requests.get(f"{API}/tasks/{wo1}/detail", headers=A, timeout=5).json()
        assert detail["task"]["notes"] == f"{TAG} replaced washer, no more drip"
        assert detail["task"]["completed_at"] and detail["task"]["duration_minutes"] is not None
        actions = {rc["action_type"] for rc in detail["receipts"]}
        assert {"task_created", "task_assigned"}.issubset(actions), actions
        # the existing task lifecycle mutates a receipt's status rather than
        # appending a "completed" receipt - assert that transition happened.
        assert any(rc.get("status") == "completed" and rc.get("completed_at") for rc in detail["receipts"]), detail["receipts"]

        # --- cross-department assignment is refused ---
        r = requests.post(f"{API}/tasks/{wo2}/assign", headers=T1, json={"assigned_to": users["hk"]["user_id"]}, timeout=5)
        assert r.status_code == 403, r.text

        # --- admin assigns wo2 to tech2 ---
        r = requests.post(f"{API}/tasks/{wo2}/assign", headers=A, json={"assigned_to": users["tech2"]["user_id"]}, timeout=5)
        assert r.status_code == 200 and r.json()["assigned_name"] == f"{TAG} tech2"

        # --- assignable roster is scoped and reachable by a lead ---
        roster = requests.get(f"{API}/staff/assignable", headers=T1, params={"department": "maintenance"}, timeout=5).json()
        ids = {u["user_id"] for u in roster}
        assert {users["tech1"]["user_id"], users["tech2"]["user_id"]}.issubset(ids)
        assert users["hk"]["user_id"] not in ids
        assert requests.get(f"{API}/staff/assignable", headers=T1, params={"department": "housekeeping"}, timeout=5).status_code == 403

        # --- department routing still works end to end ---
        rr = requests.post(f"{API}/tasks/resident-request", json={
            "category": "housekeeping", "room": f"{TAG}-RR", "summary": f"{TAG} towels please", "source": "aria_voice",
        }, timeout=5)
        assert rr.status_code == 200
        assert rr.json()["task_id"] not in {t["task_id"] for t in requests.get(f"{API}/tasks", headers=T1, timeout=5).json()}

        # --- Operations Overview reflects the same StaffTask truth ---
        ov = requests.get(f"{API}/ops/overview", headers=A, params={"attention_limit": 400}, timeout=15).json()
        by_ref = {r["ref_id"]: r for r in ov["attention"]}
        # wo3 is an unassigned maintenance WO -> tier 5, department "Maintenance"
        assert wo3 in by_ref and by_ref[wo3]["tier"] == 5 and by_ref[wo3]["department"] == "Maintenance"
        maint_dept = next(d for d in ov["departments"] if d["slug"] == "maintenance")
        assert maint_dept["open"] >= 2          # wo2 (assigned, pending) + wo3 (unassigned)
        assert ov["tasks"]["completed_today"] >= 1   # wo1
    finally:
        tids = [t["task_id"] for t in await db.staff_tasks.find(
            {"room": {"$regex": f"^{TAG}"}}, {"_id": 0, "task_id": 1},
        ).to_list(200)]
        await db.staff_tasks.delete_many({"room": {"$regex": f"^{TAG}"}})
        if tids:
            await db.receipts.delete_many({"related_object_id": {"$in": tids}})
        await db.receipts.delete_many({"room": {"$regex": f"^{TAG}"}})
        await db.users.delete_many({"email": {"$regex": f"^{TAG}_"}})


def test_maintenance_workorders():
    if not _backend_up():
        pytest.skip(f"backend not reachable at {BASE_URL}")
    asyncio.run(_run())
