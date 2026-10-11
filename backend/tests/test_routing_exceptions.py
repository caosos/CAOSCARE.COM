"""careops-routing-exceptions-001: undelivered / unassigned / overdue / failed-handoff requests
are listed with owner, age, latest action, delivery and receipts; scoped; recoverable.

    TEST_API_BASE=http://127.0.0.1:8070 pytest tests/test_routing_exceptions.py -q
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
TAG = f"rex_{uuid.uuid4().hex[:8]}"


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
    pw = "rex-pw-12345678"
    ids = {}
    for k, (role, dept) in {"nurse": ("staff", "nursing"), "cook": ("staff", "kitchen"), "fd": ("front_desk", None), "admin": ("admin", None)}.items():
        ids[k] = uid("user")
        await db.users.insert_one({"user_id": ids[k], "email": f"{TAG}_{k}@example.com", "name": f"{TAG} {k}", "role": role,
                                   "department": dept, "auth_provider": "jwt", "created_at": now_utc().isoformat(),
                                   "password_hash": bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()})
    rid = uid("res")
    await db.residents.insert_one({"resident_id": rid, "name": f"{TAG} Resident", "room": f"{TAG}-R", "created_at": now_utc().isoformat()})
    now = datetime.now(timezone.utc)
    try:
        tok = lambda k: {"Authorization": "Bearer " + requests.post(f"{API}/auth/login", json={"email": f"{TAG}_{k}@example.com", "password": pw}, timeout=5).json()["token"]}
        H = {k: tok(k) for k in ids}
        ask = lambda cat, words: _ok(requests.post(f"{API}/tasks/resident-request", json={"category": cat, "resident_id": rid, "room": f"{TAG}-R",
                                        "source": "aria_voice", "summary": words, "resident_words": words}, timeout=5))["task_id"]
        undel = ask("nursing", "Need help to the bathroom")                               # undelivered + unassigned
        deliv = ask("kitchen", "Can I get extra coffee with breakfast")                     # unassigned only (delivery confirmed)
        await db.notifications.update_many({"related_object_id": deliv}, {"$set": {"status": "delivered"}})
        failed = ask("nursing", "My knee hurts when I stand up")                            # failed handoff (all attempts failed) + unassigned
        await db.notifications.update_many({"related_object_id": failed}, {"$set": {"status": "failed"}})
        over = ask("kitchen", "Please send soup for lunch tomorrow")                         # overdue (planned date passed), owned, delivered
        await db.notifications.update_many({"related_object_id": over}, {"$set": {"status": "delivered"}})
        _ok(requests.post(f"{API}/tasks/{over}/assign", headers=H["cook"], json={"assigned_to": ids["cook"]}, timeout=5))
        await db.staff_tasks.update_one({"task_id": over}, {"$set": {"requested_for_date": (now - timedelta(days=2)).date().isoformat()}})
        clean = ask("kitchen", "Could the tea be a bit hotter please")                       # control: owned + delivered + not overdue
        await db.notifications.update_many({"related_object_id": clean}, {"$set": {"status": "delivered"}})
        _ok(requests.post(f"{API}/tasks/{clean}/assign", headers=H["cook"], json={"assigned_to": ids["cook"]}, timeout=5))
        legacy = f"{TAG}_legacy"                                                             # refused step: legacy task with no origin receipt
        await db.staff_tasks.insert_one({"task_id": legacy, "title": "Legacy request", "category": "nursing", "visibility_role": "nursing", "status": "pending",
                                         "priority": "normal", "source": "kiosk_button", "resident_id": rid, "created_at": now.isoformat(), "_tag": TAG})
        r = requests.post(f"{API}/tasks/{legacy}/start", headers=H["nurse"], timeout=5); assert r.status_code == 409, r.text
        old = f"{TAG}_old"
        await db.staff_tasks.insert_one({"task_id": old, "title": "Old request", "category": "nursing", "visibility_role": "nursing", "status": "pending",
                                         "priority": "normal", "source": "kiosk_button", "resident_id": rid, "created_at": (now - timedelta(days=40)).isoformat(), "_tag": TAG})

        allx = _ok(requests.get(f"{API}/ops/routing-exceptions", headers=H["admin"], timeout=5))
        mine = {r["task_id"]: r for r in allx["items"] if r["resident_name"] == f"{TAG} Resident" or r["task_id"].startswith(TAG)}
        assert set(mine) == {undel, deliv, failed, over, legacy}, set(mine)                # clean control absent; old (review) absent by default
        assert mine[undel]["classes"] == ["undelivered", "unassigned"]
        assert mine[deliv]["classes"] == ["unassigned"]
        assert "failed_handoff" in mine[failed]["classes"] and "undelivered" not in mine[failed]["classes"]
        assert mine[over]["classes"] == ["overdue"] and mine[over]["owner"] == f"{TAG} cook"
        assert "failed_handoff" in mine[legacy]["classes"] and mine[legacy]["escalation"]["refused_steps"] == 1
        u = mine[undel]
        assert u["delivery"]["state"] == "not_sent" and u["notification_attempts"] >= 1 and u["receipts_count"] >= 1
        assert u["latest_action"]["field"] == "created" and u["age_seconds"] >= 0 and u["currency"]["bucket"] == "current"
        # counts reconcile with the rows and with the records
        for c in ("undelivered", "unassigned", "overdue", "failed_handoff"):
            assert allx["counts"][c] == sum(1 for r in allx["items"] if c in r["classes"])
            only = _ok(requests.get(f"{API}/ops/routing-exceptions", headers=H["admin"], params={"kind": c}, timeout=5))
            assert all(c in r["classes"] for r in only["items"]) and len(only["items"]) == allx["counts"][c]
        db_unassigned = await db.staff_tasks.count_documents({"task_id": {"$in": list(mine)}, "status": {"$in": ["pending", "in_progress"]}, "assigned_to": None})
        assert db_unassigned == sum(1 for r in mine.values() if "unassigned" in r["classes"])
        assert requests.get(f"{API}/ops/routing-exceptions", headers=H["admin"], params={"kind": "bogus"}, timeout=5).status_code == 422
        rev = _ok(requests.get(f"{API}/ops/routing-exceptions", headers=H["admin"], params={"include_review": "true"}, timeout=5))
        assert old in {r["task_id"] for r in rev["items"]}
        # scoping: nursing sees nursing only; kitchen sees kitchen only; front desk (Administration) sees none of these; anonymous 401
        nv = {r["department"] for r in _ok(requests.get(f"{API}/ops/routing-exceptions", headers=H["nurse"], timeout=5))["items"]}
        kv = {r["department"] for r in _ok(requests.get(f"{API}/ops/routing-exceptions", headers=H["cook"], timeout=5))["items"]}
        assert nv <= {"nursing"} and kv <= {"kitchen"}
        assert not ({undel, deliv} & {r["task_id"] for r in _ok(requests.get(f"{API}/ops/routing-exceptions", headers=H["fd"], timeout=5))["items"]})
        assert requests.get(f"{API}/ops/routing-exceptions", timeout=5).status_code == 401
        # detail: receipts + notifications
        d = _ok(requests.get(f"{API}/ops/routing-exceptions/{undel}", headers=H["nurse"], timeout=5))
        assert d["exception"]["task_id"] == undel and d["receipts"][0]["action_type"] == "resident_request_created" and d["notifications"]
        assert requests.get(f"{API}/ops/routing-exceptions/{deliv}", headers=H["nurse"], timeout=5).status_code == 404   # other department
        # recovery: re-notify is receipted and adds a notification record; another department cannot
        before = await db.notifications.count_documents({"related_object_id": undel})
        rn = _ok(requests.post(f"{API}/ops/routing-exceptions/{undel}/renotify", headers=H["nurse"], timeout=5))
        assert rn["delivery_before"] == "not_sent" and await db.notifications.count_documents({"related_object_id": undel}) > before
        assert await db.receipts.count_documents({"related_object_id": undel, "action_type": "department_renotified"}) == 1
        assert requests.post(f"{API}/ops/routing-exceptions/{undel}/renotify", headers=H["cook"], timeout=5).status_code == 403
        # recovery through the existing assign route removes the unassigned class
        _ok(requests.post(f"{API}/tasks/{deliv}/assign", headers=H["cook"], json={"assigned_to": ids["cook"]}, timeout=5))
        after = {r["task_id"] for r in _ok(requests.get(f"{API}/ops/routing-exceptions", headers=H["admin"], timeout=5))["items"]}
        assert deliv not in after and undel in after
    finally:
        await db.users.delete_many({"email": {"$regex": f"^{TAG}_"}})
        await db.residents.delete_many({"resident_id": rid})
        tids = [x["task_id"] for x in await db.staff_tasks.find({"resident_id": rid}, {"task_id": 1}).to_list(50)]
        await db.staff_tasks.delete_many({"task_id": {"$in": tids}})
        await db.receipts.delete_many({"related_object_id": {"$in": tids}})
        await db.notifications.delete_many({"related_object_id": {"$in": tids}})


@pytest.mark.skipif(not _backend_up(), reason="backend not running")
def test_routing_exceptions_classes_scope_counts_detail_and_recovery():
    asyncio.run(_run())
