"""Worker workflow rules (#168): acknowledge, claim, start and complete are
distinct; a worker does not run overlapping simulated work; completion needs
an outcome; an owner/admin override needs a recorded reason; cancelling
needs a reason. Every refusal is a clear 4xx with a receipt and no change.

Found live 2026-10-14 22:51 CDT: a second Start in the running simulation
hit the one-active-ticket index and returned 500 ("Could not start").

    TEST_API_BASE=http://127.0.0.1:8070 pytest tests/test_task_work_rules.py -q
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
TAG = f"wrk_{uuid.uuid4().hex[:8]}"


def _up() -> bool:
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
    pw = "wrk-pw-12345678"
    ids = {}
    for k, (role, dept) in {"n1": ("staff", "nursing"), "n2": ("staff", "nursing"),
                            "admin": ("admin", None)}.items():
        ids[k] = uid("user")
        await db.users.insert_one({"user_id": ids[k], "email": f"{TAG}_{k}@example.com", "name": f"{TAG} {k}",
                                   "role": role, "department": dept, "auth_provider": "jwt",
                                   "created_at": now_utc().isoformat(),
                                   "password_hash": bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()})
    rid = uid("res")
    room = f"{TAG}-R"
    await db.residents.insert_one({"resident_id": rid, "name": f"{TAG} Resident", "room": room,
                                   "created_at": now_utc().isoformat()})
    # Open requests for one resident and department merge (repeat asks), so
    # each case uses its own resident.
    rids = {}
    for n in range(2, 6):
        rids[n] = uid("res")
        await db.residents.insert_one({"resident_id": rids[n], "name": f"{TAG} Resident {n}", "room": room,
                                       "created_at": now_utc().isoformat()})
    try:
        H = {k: {"Authorization": "Bearer " + requests.post(
            f"{API}/auth/login", json={"email": f"{TAG}_{k}@example.com", "password": pw}, timeout=5).json()["token"]}
            for k in ids}

        def ask(words, resident=None):
            return _ok(requests.post(f"{API}/tasks/resident-request", json={
                "category": "nursing", "resident_id": resident or rid, "room": room, "summary": words,
                "resident_words": words, "priority": "normal"}, timeout=5))["task_id"]

        async def refused(tid, action):
            return await db.receipts.count_documents({"related_object_id": tid, "action_type": f"task_{action}_refused"})

        # 1. acknowledging is not completing: complete on a pending request is refused
        t1 = ask(f"{TAG} towels please")
        _ok(requests.post(f"{API}/tasks/{t1}/acknowledge", headers=H["n1"], timeout=5))
        r = requests.post(f"{API}/tasks/{t1}/complete", headers=H["n1"], json={"notes": "done"}, timeout=5)
        assert r.status_code == 409 and "not been started" in r.text, r.text
        assert (await db.staff_tasks.find_one({"task_id": t1}))["status"] == "pending"
        assert await refused(t1, "complete") == 1

        # 2. claim, start, then completion needs a written outcome
        _ok(requests.post(f"{API}/tasks/{t1}/assign", headers=H["n1"], json={"assigned_to": ids["n1"]}, timeout=5))
        # someone else's claimed request: start refused, names the holder
        r = requests.post(f"{API}/tasks/{t1}/start", headers=H["n2"], timeout=5)
        assert r.status_code == 409 and "claimed by" in r.text, r.text
        _ok(requests.post(f"{API}/tasks/{t1}/start", headers=H["n1"], timeout=5))
        r = requests.post(f"{API}/tasks/{t1}/complete", headers=H["n1"], json={}, timeout=5)
        assert r.status_code == 422 and "outcome" in r.text, r.text
        r = requests.post(f"{API}/tasks/{t1}/complete", headers=H["n2"], json={"notes": "x"}, timeout=5)
        assert r.status_code == 409, r.text           # not the worker on it
        done = _ok(requests.post(f"{API}/tasks/{t1}/complete", headers=H["n1"],
                                 json={"notes": "Brought two towels"}, timeout=5))
        assert done["status"] == "completed" and done["completed_by"] == ids["n1"]

        # 3. one active simulated ticket per worker: the second start is a clear 409, not a 500
        t2, t3 = ask(f"{TAG} help me up", rids[2]), ask(f"{TAG} bathroom", rids[3])
        await db.staff_tasks.update_many({"task_id": {"$in": [t2, t3]}},
                                         {"$set": {"simulation_run_id": f"simrun:test:{TAG}"}})
        _ok(requests.post(f"{API}/tasks/{t2}/start", headers=H["n1"], timeout=5))
        before = await db.staff_tasks.find_one({"task_id": t3}, {"_id": 0})
        r = requests.post(f"{API}/tasks/{t3}/start", headers=H["n1"], timeout=5)
        assert r.status_code == 409 and "already working on" in r.text and "help me up" in r.text, r.text
        assert await db.staff_tasks.find_one({"task_id": t3}, {"_id": 0}) == before
        assert await refused(t3, "start") == 1
        _ok(requests.post(f"{API}/tasks/{t3}/start", headers=H["n2"], timeout=5))   # another worker may

        # 4. owner/admin override needs a reason, which is recorded
        t4 = ask(f"{TAG} snack", rids[4])
        r = requests.post(f"{API}/tasks/{t4}/complete", headers=H["admin"], json={"notes": "given"}, timeout=5)
        assert r.status_code == 409, r.text
        ov = _ok(requests.post(f"{API}/tasks/{t4}/complete", headers=H["admin"],
                               json={"notes": "Snack given by the front desk", "override_reason": "Worked off-system"},
                               timeout=5))
        assert ov["status"] == "completed" and ov["completion_override_reason"] == "Worked off-system"
        rc = await db.receipts.find_one({"related_object_id": t4, "action_type": "task_completed"}, {"_id": 0})
        assert rc["authority"] == "admin_override:admin" and "Worked off-system" in rc["result"]

        # 5. cancelling states its reason
        t5 = ask(f"{TAG} never mind", rids[5])
        assert requests.post(f"{API}/tasks/{t5}/skip", headers=H["n1"], json={}, timeout=5).status_code == 422
        _ok(requests.post(f"{API}/tasks/{t5}/skip", headers=H["n1"],
                          json={"notes": "Resident no longer needs help"}, timeout=5))
    finally:
        await db.users.delete_many({"email": {"$regex": f"^{TAG}_"}})
        await db.staff_tasks.delete_many({"room": room})
        await db.receipts.delete_many({"room": room})
        await db.residents.delete_many({"resident_id": {"$in": [rid, *rids.values()]}})


@pytest.mark.skipif(not _up(), reason="backend not reachable")
def test_worker_workflow_rules():
    assert os.environ.get("MONGO_URL") and os.environ.get("DB_NAME")
    asyncio.run(_run())
