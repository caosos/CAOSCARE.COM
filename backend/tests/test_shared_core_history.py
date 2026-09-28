"""Shared-core SC-1 / SC-2 across Nursing and Maintenance.

SC-1: every status change appends a receipt; no earlier receipt is ever
rewritten. SC-2: every note and lifecycle step is appended to the task's
event_log with who and when, so a completion note no longer erases the
progress notes before it. Runs the two department flows that share this
contract (nursing resident request from Aria, maintenance work order from
the admin) end to end over HTTP, plus a legacy task that predates
event_log (nothing may be backfilled).

    TEST_API_BASE=http://127.0.0.1:8070 pytest tests/test_shared_core_history.py -q
Skips cleanly if the backend is unreachable.
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

TAG = f"sch_{uuid.uuid4().hex[:8]}"
NURSE_ROOM = f"{TAG}-N1"
MAINT_ROOM = f"{TAG}-M1"
LEGACY_ROOM = f"{TAG}-L1"


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


def _post(path, headers, body=None):
    r = requests.post(f"{API}{path}", headers=headers, json=body, timeout=5)
    assert r.status_code == 200, (path, r.status_code, r.text)
    return r.json()


def _detail(task_id, headers):
    r = requests.get(f"{API}/tasks/{task_id}/detail", headers=headers, timeout=5)
    assert r.status_code == 200, r.text
    return r.json()


def _assert_append_only(receipts):
    """No receipt was rewritten: each records exactly the step it was filed for."""
    for rc in receipts:
        a = rc["action_type"]
        if a in ("task_created", "resident_request_created", "task_assigned", "task_unassigned",
                 "resident_request_re_requested"):
            assert rc["status"] == "created", rc
        elif a.startswith("task_"):
            assert a == f"task_{rc['status']}", rc


async def _run():
    from motor.motor_asyncio import AsyncIOMotorClient
    from models import uid, now_utc
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]

    pw = "sch-pw-12345678"
    users = {
        "admin": {"role": "admin", "department": None},
        "nurse": {"role": "staff", "department": "nursing"},
        "tech": {"role": "staff", "department": "maintenance"},
    }
    for k, u in users.items():
        u["user_id"] = uid("user")
        u["email"] = f"{TAG}_{k}@example.com"
        u["name"] = f"{TAG} {k}"
        await db.users.insert_one({
            "user_id": u["user_id"], "email": u["email"], "name": u["name"],
            "role": u["role"], "department": u["department"], "auth_provider": "jwt",
            "password_hash": bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode(),
            "created_at": now_utc().isoformat(),
        })

    try:
        A = _login(users["admin"]["email"], pw)
        N = _login(users["nurse"]["email"], pw)
        T = _login(users["tech"]["email"], pw)

        # ---------- NURSING: resident asks via Aria, asks again, nurse works it ----------
        body = {"category": "nursing", "room": NURSE_ROOM, "source": "aria_voice",
                "summary": "needs help going to the bathroom",
                "resident_words": "I need help going to the bathroom", "priority": "high"}
        nt = _post("/tasks/resident-request", None, body)["task_id"]
        again = _post("/tasks/resident-request", None, {**body, "resident_words": "is anyone coming?"})
        assert again["duplicate"] is True and again["task_id"] == nt

        _post(f"/tasks/{nt}/acknowledge", N)
        _post(f"/tasks/{nt}/assign", N, {"assigned_to": users["nurse"]["user_id"]})
        _post(f"/tasks/{nt}/start", N)
        for note in ("walking resident to bathroom", "resident back in chair"):
            r = requests.patch(f"{API}/tasks/{nt}", headers=N, json={"notes": note}, timeout=5)
            assert r.status_code == 200, r.text
        # saving the same note again is not a new note
        requests.patch(f"{API}/tasks/{nt}", headers=N, json={"notes": "resident back in chair"}, timeout=5)

        st = requests.get(f"{API}/tasks/resident-request/status", params={"room": NURSE_ROOM}, timeout=5).json()
        assert st["found"] and st["latest_update"] == "resident back in chair"
        assert st["latest_update_at"] and st["latest_update_at"]["iso"]
        assert "event_log" not in st  # staff history stays out of the resident view

        _post(f"/tasks/{nt}/complete", N, {"notes": "all done, call light in reach"})

        d = _detail(nt, N)
        task, log = d["task"], d["task"]["event_log"]
        assert task["notes"] == "all done, call light in reach"   # latest note stays current
        notes = [e["text"] for e in log if e["field"] == "note"]
        assert notes == ["walking resident to bathroom", "resident back in chair",
                         "all done, call light in reach"], notes           # SC-2: nothing lost
        steps = [(e["field"], e.get("to")) for e in log if e["field"] != "note"]
        assert steps == [("re_request", 1), ("acknowledged", None),
                         ("assigned_to", users["nurse"]["user_id"]),
                         ("status", "in_progress"), ("status", "completed")], steps
        staff = [e for e in log if e["field"] != "re_request"]
        assert all(e["by"] == users["nurse"]["user_id"] and e["by_name"] == users["nurse"]["name"]
                   for e in staff), staff
        rr = next(e for e in log if e["field"] == "re_request")
        assert rr["by"] == "resident" and rr["text"] == "is anyone coming?"
        ats = [e["at"] for e in log]
        assert ats == sorted(ats)

        receipts = d["receipts"]
        actions = [rc["action_type"] for rc in receipts]
        for a in ("resident_request_created", "resident_request_re_requested", "task_assigned",
                  "task_acknowledged", "task_in_progress", "task_completed"):
            assert actions.count(a) == 1, (a, actions)                    # SC-1: one receipt per step
        _assert_append_only(receipts)
        done = next(rc for rc in receipts if rc["action_type"] == "task_completed")
        assert done["room"] == NURSE_ROOM and done["assigned_role"] == "nursing"
        assert done["requested_by"] == users["nurse"]["user_id"]
        assert done["result"] == "all done, call light in reach" and done["completed_at"]

        # ---------- MAINTENANCE: admin work order, tech claims and closes it ----------
        mt = _post("/tasks", A, {"title": f"{TAG} dripping faucet", "description": "sink drips",
                                 "category": "maintenance", "visibility_role": "maintenance",
                                 "room": MAINT_ROOM})["task_id"]
        _post(f"/tasks/{mt}/assign", T, {"assigned_to": users["tech"]["user_id"]})
        _post(f"/tasks/{mt}/start", T)
        requests.patch(f"{API}/tasks/{mt}", headers=T, json={"notes": "waiting on washer part"}, timeout=5)
        _post(f"/tasks/{mt}/complete", T, {})   # no closing note: the progress note stays current

        md = _detail(mt, A)
        assert md["task"]["notes"] == "waiting on washer part"
        mlog = md["task"]["event_log"]
        assert [e["text"] for e in mlog if e["field"] == "note"] == ["waiting on washer part"]
        assert [(e["field"], e.get("to")) for e in mlog if e["field"] != "note"] == [
            ("assigned_to", users["tech"]["user_id"]), ("status", "in_progress"), ("status", "completed")]
        m_actions = [rc["action_type"] for rc in md["receipts"]]
        for a in ("task_created", "task_assigned", "task_in_progress", "task_completed"):
            assert m_actions.count(a) == 1, (a, m_actions)
        _assert_append_only(md["receipts"])

        # ---------- departments still isolated ----------
        seen_n = {t["task_id"] for t in requests.get(f"{API}/tasks", headers=N, timeout=5).json()}
        seen_t = {t["task_id"] for t in requests.get(f"{API}/tasks", headers=T, timeout=5).json()}
        assert nt in seen_n and mt not in seen_n
        assert mt in seen_t and nt not in seen_t

        # ---------- legacy task: no event_log, nothing backfilled ----------
        lt = uid("task")
        await db.staff_tasks.insert_one({
            "task_id": lt, "title": f"{TAG} legacy", "category": "nursing", "status": "pending",
            "visibility_role": "nursing", "room": LEGACY_ROOM, "priority": "normal",
            "source": "staff", "notes": "old note", "created_at": now_utc().isoformat(),
        })
        _post(f"/tasks/{lt}/acknowledge", N)   # no receipt exists: nothing to append to
        ld = _detail(lt, N)
        assert [e["field"] for e in ld["task"]["event_log"]] == ["acknowledged"]
        assert ld["receipts"] == []
    finally:
        tids = [t["task_id"] for t in await db.staff_tasks.find(
            {"room": {"$regex": f"^{TAG}"}}, {"_id": 0, "task_id": 1}).to_list(50)]
        await db.staff_tasks.delete_many({"room": {"$regex": f"^{TAG}"}})
        if tids:
            await db.receipts.delete_many({"related_object_id": {"$in": tids}})
        await db.receipts.delete_many({"room": {"$regex": f"^{TAG}"}})
        await db.users.delete_many({"email": {"$regex": f"^{TAG}_"}})


def test_shared_core_history_nursing_and_maintenance():
    if not _backend_up():
        pytest.skip(f"backend not reachable at {BASE_URL}")
    asyncio.run(_run())
