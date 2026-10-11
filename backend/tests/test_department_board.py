"""Owner review P1 Departments & staff: the department board shows members and
roles, open work by named worker with its dispatch trail, and completed history
with receipts; readable by admins and the department's own people only.

    TEST_API_BASE=http://127.0.0.1:8070 pytest tests/test_department_board.py -q
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
TAG = f"dbd_{uuid.uuid4().hex[:8]}"


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
    pw = "dbd-pw-12345678"
    people = {"hk1": ("staff", "housekeeping"), "hk2": ("staff", "housekeeping"), "nurse": ("staff", "nursing"),
              "fd": ("front_desk", None), "admin": ("admin", None)}
    ids, names = {}, {}
    for k, (role, dept) in people.items():
        ids[k], names[k] = uid("user"), f"{TAG} {k}"
        await db.users.insert_one({"user_id": ids[k], "email": f"{TAG}_{k}@example.com", "name": names[k], "role": role,
                                   "department": dept, "auth_provider": "jwt", "created_at": now_utc().isoformat(),
                                   "password_hash": bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()})
    room = f"{TAG}-R"
    rid = uid("res")
    await db.residents.insert_one({"resident_id": rid, "name": f"{TAG} Resident", "preferred_name": "Pat", "room": room, "created_at": now_utc().isoformat()})
    try:
        H = {k: _login(f"{TAG}_{k}@example.com", pw) for k in people}

        def ask(summary, category="housekeeping"):
            return _ok(requests.post(f"{API}/tasks/resident-request", headers=H["fd"], json={
                "category": category, "resident_id": rid, "source": "front_desk", "summary": summary, "resident_words": summary}, timeout=5))["task_id"]

        a = ask("Please change the bed linens")
        b = ask("The bathroom floor needs mopping")
        c = ask("Trash can is full")
        # dispatch: admin assigns a to hk1; hk1 acknowledges + starts; hk2 claims b; c stays unassigned; a completed with a note
        _ok(requests.post(f"{API}/tasks/{a}/assign", headers=H["admin"], json={"assigned_to": ids["hk1"]}, timeout=5))
        _ok(requests.post(f"{API}/tasks/{a}/acknowledge", headers=H["hk1"], timeout=5))
        _ok(requests.post(f"{API}/tasks/{a}/start", headers=H["hk1"], timeout=5))
        _ok(requests.post(f"{API}/tasks/{b}/assign", headers=H["hk2"], json={"assigned_to": ids["hk2"]}, timeout=5))
        _ok(requests.post(f"{API}/tasks/{a}/complete", headers=H["hk1"], json={"notes": "fresh linens on"}, timeout=5))

        board = _ok(requests.get(f"{API}/departments/housekeeping/board", headers=H["admin"], timeout=5))
        assert board["department"]["slug"] == "housekeeping"
        mem = {m["user_id"]: m for m in board["members"]}
        assert ids["hk1"] in mem and ids["hk2"] in mem and ids["nurse"] not in mem and ids["fd"] not in mem
        assert mem[ids["hk1"]]["role"] == "staff" and "email" not in mem[ids["hk1"]]
        groups = {g["name"]: g for g in board["by_worker"]}
        assert groups["Unassigned"]["work"] and c in [r["task_id"] for r in groups["Unassigned"]["work"]]
        assert [r["task_id"] for r in groups[names["hk2"]]["work"]] == [b]
        assert groups[names["hk1"]]["work"] == []                     # a is completed, so it left the open work
        rb = {r["task_id"]: r for g in board["by_worker"] for r in g["work"]}
        assert rb[b]["lifecycle"] == "acknowledged" and rb[b]["assigned_name"] == names["hk2"]
        assert rb[b]["trail"][0]["field"] == "created" and rb[b]["trail"][0]["text"] == "front desk"
        assert any(e["field"] == "assigned_to" and e["by_name"] == names["hk2"] and e["at"] for e in rb[b]["trail"])
        # completed history carries who/when/duration/note/receipts and the full trail
        hist = {r["task_id"]: r for r in board["history"]}
        assert a in hist and hist[a]["status"] == "completed" and hist[a]["completed_by_name"] == names["hk1"]
        assert hist[a]["notes"] == "fresh linens on" and hist[a]["duration_minutes"] is not None
        assert hist[a]["receipts_count"] >= 5                           # created, assigned, acknowledged, started, completed(+note)
        fields = [e["field"] for e in hist[a]["trail"]]
        assert fields[0] == "created" and "assigned_to" in fields and "acknowledged" in fields and "status" in fields
        assert all(e["at"] for e in hist[a]["trail"])
        # the board is department-wide (other residents' work shows too); count this test's own rows
        own = [r for g in board["by_worker"] for r in g["work"] if r["resident_name"] == f"{TAG} Resident"]
        assert len(own) == 2 and sum(1 for r in own if not r["assigned_to"]) == 1 and sum(1 for r in own if r["lifecycle"] == "acknowledged") == 1
        cnt = board["counts"]
        assert cnt["open"] >= 2 and cnt["unassigned"] >= 1 and cnt["completed_today"] >= 1
        assert board["can_assign"] is True

        # a housekeeping member sees their own board; nursing and the front desk cannot see housekeeping
        own = _ok(requests.get(f"{API}/departments/housekeeping/board", headers=H["hk1"], timeout=5))  # noqa: F841 (reuse name)
        assert own["counts"]["open"] >= 2 and own["can_assign"] is True
        assert requests.get(f"{API}/departments/housekeeping/board", headers=H["nurse"], timeout=5).status_code == 403
        assert requests.get(f"{API}/departments/housekeeping/board", headers=H["fd"], timeout=5).status_code == 403
        assert requests.get(f"{API}/departments/housekeeping/board", timeout=5).status_code == 401
        # front desk acts for Administration and sees that board, with front-desk users as members
        adm = _ok(requests.get(f"{API}/departments/administration/board", headers=H["fd"], timeout=5))
        assert ids["fd"] in {m["user_id"] for m in adm["members"]}
        assert requests.get(f"{API}/departments/no-such-dept/board", headers=H["admin"], timeout=5).status_code == 404
        # reassign through the canonical route and the board follows
        _ok(requests.post(f"{API}/tasks/{c}/assign", headers=H["admin"], json={"assigned_to": ids["hk1"]}, timeout=5))
        board2 = _ok(requests.get(f"{API}/departments/housekeeping/board", headers=H["admin"], timeout=5))
        g2 = {g["name"]: g for g in board2["by_worker"]}
        assert [r["task_id"] for r in g2[names["hk1"]]["work"]] == [c] and c not in [r["task_id"] for r in g2["Unassigned"]["work"]]
    finally:
        await db.users.delete_many({"email": {"$regex": f"^{TAG}_"}})
        await db.residents.delete_many({"resident_id": rid})
        tids = [t["task_id"] for t in await db.staff_tasks.find({"resident_id": rid}, {"task_id": 1}).to_list(50)]
        await db.staff_tasks.delete_many({"task_id": {"$in": tids}})
        await db.receipts.delete_many({"related_object_id": {"$in": tids}})
        await db.notifications.delete_many({"related_object_id": {"$in": tids}})


@pytest.mark.skipif(not _backend_up(), reason="backend not running")
def test_department_board_members_work_by_worker_trail_history_and_authorization():
    asyncio.run(_run())
