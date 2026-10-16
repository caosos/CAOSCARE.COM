"""careops-frontdesk-reopen-001: reopening a completed Front Desk request is an
explicit, receipted action (the one SC-14 left room for).

- front desk reopens a completed Administration request with a reason: the
  request is pending again with its assignee kept, the closing fields are
  cleared, the reason is in event_log, and ONE `task_reopened` receipt is
  chained to the origin (parent = the completion receipt, same workflow id,
  before/after state, authenticated front-desk actor) and carries the
  event_log entries' receipt id;
- Aria's resident status reports it as open again (not "taken care of");
- a reopen without a reason is refused (422) and nothing is written;
- a reopen of a request that is still open is refused (409), recorded as
  `task_reopen_refused`, nothing changed;
- nursing staff cannot reopen an Administration request (403, nothing written);
- an admin can reopen (admin_override); a second completion after the reopen
  works and the chain stays unbroken.

    TEST_API_BASE=http://127.0.0.1:8070 pytest tests/test_frontdesk_reopen.py -q
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
TAG = f"fdr_{uuid.uuid4().hex[:8]}"


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
    pw = "fdr-pw-12345678"
    people = {"admin": ("admin", None), "nurse": ("staff", "nursing"), "fd": ("front_desk", None)}
    ids, names = {}, {}
    for k, (role, dept) in people.items():
        ids[k], names[k] = uid("user"), f"{TAG} {k}"
        await db.users.insert_one({
            "user_id": ids[k], "email": f"{TAG}_{k}@example.com", "name": names[k], "role": role,
            "department": dept, "auth_provider": "jwt", "created_at": now_utc().isoformat(),
            "password_hash": bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode(),
        })
    room = f"{TAG}-R"
    try:
        H = {k: _login(f"{TAG}_{k}@example.com", pw) for k in people}
        words = "Callback about weekend visitor parking"
        # raised from the room (Aria voice) so the resident status endpoint covers it;
        # the front desk then works it as the Administration department
        t = _ok(requests.post(f"{API}/tasks/resident-request", json={
            "category": "administration", "room": room, "source": "aria_voice", "summary": words,
            "resident_words": words}, timeout=5))["task_id"]

        # still open -> reopen is refused and recorded; nothing changed
        r = requests.post(f"{API}/tasks/{t}/reopen", headers=H["fd"], json={"reason": "x"}, timeout=5)
        assert r.status_code == 409, r.text
        doc = await db.staff_tasks.find_one({"task_id": t}, {"_id": 0})
        assert doc["status"] == "pending" and not doc.get("event_log")
        assert await db.receipts.count_documents({"related_object_id": t, "action_type": "task_reopen_refused"}) == 1

        _ok(requests.post(f"{API}/tasks/{t}/assign", headers=H["fd"], json={"assigned_to": ids["fd"]}, timeout=5))
        _ok(requests.post(f"{API}/tasks/{t}/start", headers=H["fd"], timeout=5))
        _ok(requests.post(f"{API}/tasks/{t}/complete", headers=H["fd"], json={"notes": "pass issued"}, timeout=5))
        done = await db.staff_tasks.find_one({"task_id": t}, {"_id": 0})
        assert done["status"] == "completed" and done["completed_at"]
        receipts_before = await db.receipts.count_documents({"related_object_id": t})
        completion = await db.receipts.find_one({"related_object_id": t, "action_type": "task_completed"}, {"_id": 0})

        # no reason -> 422, nothing written
        r = requests.post(f"{API}/tasks/{t}/reopen", headers=H["fd"], json={"reason": "  "}, timeout=5)
        assert r.status_code == 422, r.text
        assert await db.receipts.count_documents({"related_object_id": t}) == receipts_before

        # nursing staff -> 403, nothing written
        r = requests.post(f"{API}/tasks/{t}/reopen", headers=H["nurse"], json={"reason": "not mine"}, timeout=5)
        assert r.status_code == 403, r.text
        assert await db.receipts.count_documents({"related_object_id": t}) == receipts_before
        assert (await db.staff_tasks.find_one({"task_id": t}, {"_id": 0}))["status"] == "completed"

        # front desk reopens with a reason
        reason = "Resident called back: the pass was never issued"
        after = _ok(requests.post(f"{API}/tasks/{t}/reopen", headers=H["fd"], json={"reason": reason}, timeout=5))
        assert after["status"] == "pending" and after["assigned_to"] == ids["fd"]
        assert after.get("completed_at") is None and after.get("completed_by") is None and after.get("started_at") is None
        assert after["reopen_count"] == 1 and after["reopened_at"] and after["notes"] == reason
        doc = await db.staff_tasks.find_one({"task_id": t}, {"_id": 0})
        rec = await db.receipts.find_one({"related_object_id": t, "action_type": "task_reopened"}, {"_id": 0})
        assert rec and rec["parent_receipt_id"] == completion["receipt_id"]
        assert rec["correlation_id"] == completion["correlation_id"]
        assert rec["before_state"]["status"] == "completed" and rec["after_state"]["status"] == "pending"
        assert rec["after_state"]["assigned_to"] == ids["fd"]
        assert rec["actor_id"] == ids["fd"] and rec["identity_basis"] == "authenticated"
        assert rec["actor_type"] == "real-human" and rec["authority"] == "assignee"
        assert rec["result"] == reason and rec["next_state"] == "awaiting_start"
        assert await db.receipts.count_documents({"related_object_id": t, "action_type": "task_reopened"}) == 1
        entries = [e for e in doc["event_log"] if e.get("receipt_id") == rec["receipt_id"]]
        assert [e["field"] for e in entries] == ["note", "status"]
        assert entries[0]["text"] == reason and entries[1]["from"] == "completed" and entries[1]["to"] == "pending"
        # history before the reopen is intact
        assert any(e["field"] == "status" and e["to"] == "completed" for e in doc["event_log"])

        # Aria: open again, not "taken care of"
        s = _ok(requests.get(f"{API}/tasks/resident-request/status", params={"room": room}, timeout=5))
        assert s["found"] and s["task_id"] == t and s["lifecycle"] == "acknowledged"
        assert "taken care of" not in s["spoken"] and names["fd"] in s["spoken"]

        # admin reopen after a second completion, then complete again: chain unbroken
        # a reopened request is pending again: it is started before it is completed (#168)
        _ok(requests.post(f"{API}/tasks/{t}/start", headers=H["fd"], timeout=5))
        _ok(requests.post(f"{API}/tasks/{t}/complete", headers=H["fd"], json={"notes": "done twice"}, timeout=5))
        again = _ok(requests.post(f"{API}/tasks/{t}/reopen", headers=H["admin"], json={"reason": "audit"}, timeout=5))
        assert again["reopen_count"] == 2
        rec2 = await db.receipts.find_one({"related_object_id": t, "action_type": "task_reopened", "result": "audit"}, {"_id": 0})
        assert rec2["authority"] == "admin_override:admin"
        _ok(requests.post(f"{API}/tasks/{t}/start", headers=H["fd"], timeout=5))
        _ok(requests.post(f"{API}/tasks/{t}/complete", headers=H["fd"], json={"notes": "final"}, timeout=5))
        chain = [r async for r in db.receipts.find({"related_object_id": t, "action_type": {"$not": {"$regex": "_refused$"}}}, {"_id": 0}).sort("created_at", 1)]
        for prev, cur in zip(chain, chain[1:]):
            assert cur["parent_receipt_id"] == prev["receipt_id"], (prev["action_type"], cur["action_type"])
        assert {r["correlation_id"] for r in chain} == {chain[0]["receipt_id"]}
    finally:
        await db.users.delete_many({"email": {"$regex": f"^{TAG}_"}})
        await db.staff_tasks.delete_many({"room": room})
        await db.receipts.delete_many({"room": room})
        await db.notifications.delete_many({"room": room})


@pytest.mark.skipif(not _backend_up(), reason="backend not reachable")
def test_frontdesk_reopen():
    assert os.environ.get("MONGO_URL") and os.environ.get("DB_NAME")
    asyncio.run(_run())
