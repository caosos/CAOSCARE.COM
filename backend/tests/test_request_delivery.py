"""careops-routing-delivery-audit-001: every routed request says truthfully whether its
department was actually reached (detail, department board, operations overview).

    TEST_API_BASE=http://127.0.0.1:8070 pytest tests/test_request_delivery.py -q
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
TAG = f"rdl_{uuid.uuid4().hex[:8]}"


def test_summary_states_best_evidence_first():
    from routes.request_delivery import summarize
    s = lambda *st: summarize([{"status": x, "to": "a@x", "route": "department_staff"} for x in st])
    assert summarize([])["state"] == "none" and summarize([])["reached"] is False
    assert s("logged")["state"] == "not_sent" and "NOT notified" in s("logged")["label"]
    assert s("failed", "bounced")["state"] == "failed" and s("failed")["reached"] is False
    assert s("logged", "sent")["state"] == "sent" and s("sent")["reached"] is True
    assert s("sent", "delivered")["state"] == "delivered"
    assert s("simulated")["state"] == "simulated" and s("simulated")["reached"] is False
    assert s("failed", "logged")["state"] == "not_sent"


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
    pw = "rdl-pw-12345678"
    ids = {}
    for k, (role, dept) in {"cook": ("staff", "kitchen"), "admin": ("admin", None)}.items():
        ids[k] = uid("user")
        await db.users.insert_one({"user_id": ids[k], "email": f"{TAG}_{k}@example.com", "name": f"{TAG} {k}", "role": role,
                                   "department": dept, "auth_provider": "jwt", "created_at": now_utc().isoformat(),
                                   "password_hash": bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()})
    rid = uid("res")
    await db.residents.insert_one({"resident_id": rid, "name": f"{TAG} Resident", "room": f"{TAG}-R", "created_at": now_utc().isoformat()})
    try:
        tok = lambda k: {"Authorization": "Bearer " + requests.post(f"{API}/auth/login", json={"email": f"{TAG}_{k}@example.com", "password": pw}, timeout=5).json()["token"]}
        H = {k: tok(k) for k in ids}
        # a resident asks through the room-screen bus (no provider configured on the test backend)
        t = _ok(requests.post(f"{API}/tasks/resident-request", json={"category": "kitchen", "resident_id": rid, "room": f"{TAG}-R",
                "source": "aria_voice", "summary": "Asks what is for supper", "resident_words": "What's for supper tonight?"}, timeout=5))["task_id"]
        d = _ok(requests.get(f"{API}/tasks/{t}/detail", headers=H["admin"], timeout=5))["delivery"]
        assert d["state"] == "not_sent" and d["reached"] is False and f"{TAG}_cook@example.com" in d["to"], d
        b = _ok(requests.get(f"{API}/departments/kitchen/board", headers=H["cook"], timeout=5))
        row = [r for g in b["by_worker"] for r in g["work"] if r["task_id"] == t][0]
        assert row["delivery"]["state"] == "not_sent" and b["counts"]["not_notified"] >= 1
        ov = _ok(requests.get(f"{API}/ops/overview", headers=H["admin"], params={"attention_limit": 400}, timeout=5))
        att = [a for a in ov["attention"] if a["ref_id"] == t][0]
        assert att["delivery"]["state"] == "not_sent" and ov["tasks"]["not_notified_open"] >= 1
        # once the provider reports delivery, the same request reads as reached everywhere
        await db.notifications.update_many({"related_object_id": t}, {"$set": {"status": "delivered"}})
        assert _ok(requests.get(f"{API}/tasks/{t}/detail", headers=H["admin"], timeout=5))["delivery"]["state"] == "delivered"
        ov = _ok(requests.get(f"{API}/ops/overview", headers=H["admin"], params={"attention_limit": 400}, timeout=5))
        assert [a for a in ov["attention"] if a["ref_id"] == t][0]["delivery"]["reached"] is True
        # a request with no notification record at all says so (never silently "fine")
        await db.notifications.delete_many({"related_object_id": t})
        assert _ok(requests.get(f"{API}/tasks/{t}/detail", headers=H["admin"], timeout=5))["delivery"]["state"] == "none"
    finally:
        await db.users.delete_many({"email": {"$regex": f"^{TAG}_"}})
        await db.residents.delete_many({"resident_id": rid})
        tids = [x["task_id"] for x in await db.staff_tasks.find({"resident_id": rid}, {"task_id": 1}).to_list(20)]
        await db.staff_tasks.delete_many({"task_id": {"$in": tids}})
        await db.receipts.delete_many({"related_object_id": {"$in": tids}})
        await db.notifications.delete_many({"related_object_id": {"$in": tids}})


@pytest.mark.skipif(not _backend_up(), reason="backend not running")
def test_delivery_truth_on_detail_board_and_overview():
    asyncio.run(_run())
