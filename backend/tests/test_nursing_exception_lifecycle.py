"""careops-nursing-exception-lifecycle-001: a nurse who can't complete a
request sends it to a supervisor (request stays open, unassigned, flagged);
an owner/admin reviews it; it is reassigned and completed. Every step has a
chained receipt, the resident/Aria status is truthful at each state, and
other roles are refused with nothing written.

    TEST_API_BASE=http://127.0.0.1:8070 pytest tests/test_nursing_exception_lifecycle.py -q
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
TAG = f"nex_{uuid.uuid4().hex[:8]}"


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
    pw = "nex-pw-12345678"
    ids = {}
    for k, (role, dept) in {"n1": ("staff", "nursing"), "n2": ("staff", "nursing"), "maint": ("staff", "maintenance"),
                            "fd": ("front_desk", None), "admin": ("admin", None)}.items():
        ids[k] = uid("user")
        await db.users.insert_one({"user_id": ids[k], "email": f"{TAG}_{k}@example.com", "name": f"{TAG} {k}", "role": role,
                                   "department": dept, "auth_provider": "jwt", "created_at": now_utc().isoformat(),
                                   "password_hash": bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()})
    rid = uid("res")
    room = f"{TAG}-R"
    await db.residents.insert_one({"resident_id": rid, "name": f"{TAG} Resident", "room": room, "created_at": now_utc().isoformat()})
    try:
        H = {k: {"Authorization": "Bearer " + requests.post(f"{API}/auth/login", json={"email": f"{TAG}_{k}@example.com", "password": pw}, timeout=5).json()["token"]} for k in ids}
        status = lambda: _ok(requests.get(f"{API}/tasks/resident-request/status", params={"resident_id": rid}, timeout=5))
        t = _ok(requests.post(f"{API}/tasks/resident-request", json={"category": "nursing", "resident_id": rid, "room": room,
                                                                     "summary": "help to the bathroom", "resident_words": "I need help going to the bathroom",
                                                                     "priority": "high"}, timeout=5))
        tid = t["task_id"]
        _ok(requests.post(f"{API}/tasks/{tid}/assign", headers=H["n1"], json={"assigned_to": ids["n1"]}, timeout=5))
        _ok(requests.post(f"{API}/tasks/{tid}/start", headers=H["n1"], timeout=5))
        assert "working on it now" in status()["spoken"]

        # refusals: no reason; another department; front desk (not its department)
        assert requests.post(f"{API}/tasks/{tid}/escalate", headers=H["n1"], json={"reason": ""}, timeout=5).status_code == 422
        before = await db.receipts.count_documents({"related_object_id": tid})
        assert requests.post(f"{API}/tasks/{tid}/escalate", headers=H["maint"], json={"reason": "x"}, timeout=5).status_code == 403
        assert requests.post(f"{API}/tasks/{tid}/escalate", headers=H["fd"], json={"reason": "x"}, timeout=5).status_code == 403
        assert await db.receipts.count_documents({"related_object_id": tid}) == before

        # can't complete -> open, unassigned, flagged, receipted
        e = _ok(requests.post(f"{API}/tasks/{tid}/escalate", headers=H["n1"], json={"reason": "Needs two people for the transfer"}, timeout=5))
        doc = await db.staff_tasks.find_one({"task_id": tid})
        assert doc["needs_review"] and doc["status"] == "pending" and doc["assigned_to"] is None
        r = await db.receipts.find_one({"receipt_id": e["receipt_id"]})
        assert r["action_type"] == "task_escalated" and r["before_state"]["status"] == "in_progress"
        assert r["after_state"]["needs_review"] is True and r["authority"] == "assignee"
        s = status()
        assert s["is_open"] and "supervisor" in s["spoken"] and "working on it" not in s["spoken"]
        ex = _ok(requests.get(f"{API}/ops/routing-exceptions", headers=H["admin"], params={"kind": "needs_review"}, timeout=5))
        assert tid in {row["task_id"] for row in ex["items"]}

        # review: nurse refused (403, nothing written); admin needs a note; admin reviews
        before = await db.receipts.count_documents({"related_object_id": tid})
        assert requests.post(f"{API}/tasks/{tid}/review", headers=H["n2"], json={"reason": "ok"}, timeout=5).status_code == 403
        assert await db.receipts.count_documents({"related_object_id": tid}) == before
        assert requests.post(f"{API}/tasks/{tid}/review", headers=H["admin"], json={"reason": ""}, timeout=5).status_code == 422
        v = _ok(requests.post(f"{API}/tasks/{tid}/review", headers=H["admin"], json={"reason": "Send the evening nurse with an aide"}, timeout=5))
        assert requests.post(f"{API}/tasks/{tid}/review", headers=H["admin"], json={"reason": "again"}, timeout=5).status_code == 409
        doc = await db.staff_tasks.find_one({"task_id": tid})
        assert not doc["needs_review"] and doc["reviewed_by_name"]

        # reassign to another nurse, complete; truthful status at each step
        _ok(requests.post(f"{API}/tasks/{tid}/assign", headers=H["admin"], json={"assigned_to": ids["n2"]}, timeout=5))
        assert "has taken it on" in status()["spoken"]
        _ok(requests.post(f"{API}/tasks/{tid}/complete", headers=H["n2"], json={"notes": "Done with an aide"}, timeout=5))
        hist = _ok(requests.get(f"{API}/tasks/resident-request/history", params={"resident_id": rid}, timeout=5))
        assert hist["requests"][0]["task_id"] == tid

        # one linked chain; every history entry carries its receipt id
        chain = await db.receipts.find({"related_object_id": tid, "action_type": {"$not": {"$regex": "_refused$"}}}).sort("created_at", 1).to_list(50)
        kinds = [c["action_type"] for c in chain]
        for want in ("resident_request_created", "task_escalated", "task_reviewed", "task_completed"):
            assert want in kinds, kinds
        assert len({c.get("correlation_id") for c in chain[1:]}) == 1
        doc = await db.staff_tasks.find_one({"task_id": tid})
        fields = [x["field"] for x in doc["event_log"]]
        assert "escalated" in fields and "reviewed" in fields
        assert all(x.get("receipt_id") for x in doc["event_log"])
        assert v["receipt_id"] in {c["receipt_id"] for c in chain}
    finally:
        await db.users.delete_many({"email": {"$regex": f"^{TAG}_"}})
        await db.residents.delete_many({"resident_id": rid})
        tids = [x["task_id"] for x in await db.staff_tasks.find({"resident_id": rid}, {"task_id": 1}).to_list(20)]
        await db.staff_tasks.delete_many({"task_id": {"$in": tids}})
        await db.receipts.delete_many({"related_object_id": {"$in": tids}})
        await db.notifications.delete_many({"related_object_id": {"$in": tids}})


@pytest.mark.skipif(not _up(), reason="backend not running")
def test_nursing_exception_lifecycle():
    asyncio.run(_run())
