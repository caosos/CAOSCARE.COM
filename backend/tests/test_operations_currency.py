"""careops-current-operations-truth-001: open alerts/tasks are classified as current,
current simulation, past simulation or needs-review; screens default to current work;
an administrator closes reviewed legacy records through receipted paths, and an
emergency needs a written human disposition.

    TEST_API_BASE=http://127.0.0.1:8070 pytest tests/test_operations_currency.py -q
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
TAG = f"ocu_{uuid.uuid4().hex[:8]}"


def test_classify_rules():
    from routes.operations_currency import classify
    now = datetime.now(timezone.utc)
    ago = lambda **kw: (now - timedelta(**kw)).isoformat()
    assert classify({"created_at": ago(hours=2)}, "alert", None, now)["bucket"] == "current"
    old = classify({"created_at": ago(days=40)}, "alert", None, now)
    assert old["bucket"] == "review" and "no resident" in old["reason"]
    assert "test / mock" in classify({"created_at": ago(days=40), "resident_id": "r", "resident_name": "MOCK Eleanor"}, "alert", None, now)["reason"]
    assert "real or unknown" in classify({"created_at": ago(days=40), "resident_id": "r", "resident_name": "Helen Torres"}, "alert", None, now)["reason"]
    assert classify({"created_at": ago(days=10)}, "task", None, now)["bucket"] == "current"      # tasks: 14-day window
    assert classify({"created_at": ago(days=20)}, "task", None, now)["bucket"] == "review"
    assert classify({"simulated": True, "simulation_run_id": "run1", "created_at": ago(days=90)}, "task", "run1", now)["bucket"] == "sim_current"
    assert classify({"simulated": True, "simulation_run_id": "run0", "created_at": ago(hours=1)}, "task", "run1", now)["bucket"] == "sim_past"


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
    pw = "ocu-pw-12345678"
    ids = {}
    for k, (role, dept) in {"nurse": ("staff", "nursing"), "admin": ("admin", None)}.items():
        ids[k] = uid("user")
        await db.users.insert_one({"user_id": ids[k], "email": f"{TAG}_{k}@example.com", "name": f"{TAG} {k}", "role": role,
                                   "department": dept, "auth_provider": "jwt", "created_at": now_utc().isoformat(),
                                   "password_hash": bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()})
    now = datetime.now(timezone.utc)
    ago = lambda **kw: (now - timedelta(**kw)).isoformat()
    run_id = f"simrun_{TAG}"
    had_running = await db.sim_runs.count_documents({"state": {"$in": ["RUNNING", "PAUSED"]}})
    if not had_running:
        await db.sim_runs.insert_one({"run_id": run_id, "scenario": "nursing_assist", "state": "RUNNING", "cursor": 1,
                                      "started_at": now.isoformat(), "updated_at": now.isoformat(), "_tag": TAG})
    A = lambda aid, **kw: {"alert_id": f"{TAG}_{aid}", "status": "active", "severity": "assist", "created_at": ago(hours=1), "_tag": TAG, **kw}
    alerts = [A("fresh", resident_id="r1", resident_name=f"{TAG} Real"),
              A("old_assist", created_at=ago(days=40)),
              A("old_emerg", severity="emergency", created_at=ago(days=30), resident_id="r2", resident_name="MOCK Someone"),
              A("sim_now", simulated=True, simulation_run_id=run_id)]
    await db.alerts.insert_many(alerts)
    T = lambda tid, **kw: {"task_id": f"{TAG}_{tid}", "title": tid, "category": "nursing", "visibility_role": "nursing", "status": "pending",
                           "priority": "normal", "source": "kiosk_button", "created_at": ago(hours=3), "_tag": TAG, **kw}
    tasks = [T("fresh"), T("old", created_at=ago(days=49), resident_name="MOCK Eleanor Whitfield"),
             T("sim_now", simulated=True, simulation_run_id=run_id), T("sim_past", simulated=True, simulation_run_id="simrun_gone")]
    await db.staff_tasks.insert_many(tasks)
    # the lifecycle refuses tasks with no origin receipt; give the old one an origin like a real request has
    from routes.receipts import create_receipt
    await create_receipt(action_type="resident_request_created", related_object_type="task", related_object_id=f"{TAG}_old",
                         status="created", provenance={"correlation_id": f"rc_{TAG}", "authority": "test_seed"})
    try:
        tok = lambda k: {"Authorization": "Bearer " + requests.post(f"{API}/auth/login", json={"email": f"{TAG}_{k}@example.com", "password": pw}, timeout=5).json()["token"]}
        H = {k: tok(k) for k in ids}
        mine = lambda rows, key: {r[key] for r in rows if r[key].startswith(TAG)}
        allv = _ok(requests.get(f"{API}/alerts", headers=H["admin"], params={"limit": 2000}, timeout=5))
        cur = {r["alert_id"]: r["currency"]["bucket"] for r in allv if r["alert_id"].startswith(TAG)}
        assert cur == {f"{TAG}_fresh": "current", f"{TAG}_old_assist": "review", f"{TAG}_old_emerg": "review",
                       f"{TAG}_sim_now": "sim_current" if not had_running else "sim_past"}, cur
        cv = mine(_ok(requests.get(f"{API}/alerts", headers=H["admin"], params={"limit": 2000, "view": "current"}, timeout=5)), "alert_id")
        rv = mine(_ok(requests.get(f"{API}/alerts", headers=H["admin"], params={"limit": 2000, "view": "review"}, timeout=5)), "alert_id")
        assert f"{TAG}_fresh" in cv and f"{TAG}_old_assist" not in cv and {f"{TAG}_old_assist", f"{TAG}_old_emerg"} <= rv
        tc = mine(_ok(requests.get(f"{API}/tasks", headers=H["nurse"], params={"view": "current"}, timeout=5)), "task_id")
        tr = mine(_ok(requests.get(f"{API}/tasks", headers=H["nurse"], params={"view": "review"}, timeout=5)), "task_id")
        assert f"{TAG}_fresh" in tc and f"{TAG}_old" not in tc and {f"{TAG}_old", f"{TAG}_sim_past"} <= tr
        if not had_running:
            assert f"{TAG}_sim_now" in tc
        c = _ok(requests.get(f"{API}/ops/currency", headers=H["admin"], timeout=5))
        assert c["alerts"]["review"] >= 2 and c["alerts"]["review_emergencies"] >= 1 and c["tasks"]["review"] >= 1
        if not had_running:
            assert c["simulator"]["active_run_id"] == run_id and c["simulator"]["state"] == "RUNNING"
        assert requests.get(f"{API}/ops/currency", headers=H["nurse"], timeout=5).status_code == 403
        # legacy close: current refused, emergency without disposition refused, non-emergency closed with a receipt
        lc = lambda body, h="admin": requests.post(f"{API}/ops/legacy/close", headers=H[h], json=body, timeout=5)
        assert lc({"kind": "alert", "ids": [f"{TAG}_old_assist"], "reason": "test"}, "nurse").status_code == 403
        r = _ok(lc({"kind": "alert", "ids": [f"{TAG}_fresh", f"{TAG}_old_emerg", f"{TAG}_old_assist"], "reason": "RF bring-up test activations"}))
        assert r["closed"] == 1 and {x["id"] for x in r["refused"]} == {f"{TAG}_fresh", f"{TAG}_old_emerg"}
        assert any("disposition" in x["why"] for x in r["refused"])
        a = await db.alerts.find_one({"alert_id": f"{TAG}_old_assist"}, {"_id": 0})
        assert a["status"] == "resolved" and a["outcome"] == "legacy_review_closed" and "RF bring-up" in a["close_notes"]
        rc = await db.receipts.find_one({"related_object_id": f"{TAG}_old_assist", "action_type": "alert_legacy_closed"}, {"_id": 0})
        assert rc and rc["actor_name"] == f"{TAG} admin" and rc["before_state"]["status"] == "active"
        assert (await db.alerts.find_one({"alert_id": f"{TAG}_fresh"}))["status"] == "active"
        r = _ok(lc({"kind": "alert", "ids": [f"{TAG}_old_emerg"], "reason": "mock resident test press", "disposition": "Checked with nursing: test press"}))
        e = await db.alerts.find_one({"alert_id": f"{TAG}_old_emerg"}, {"_id": 0})
        assert r["closed"] == 1 and "Disposition: Checked with nursing" in e["close_notes"]
        # tasks close through the canonical receipted skip; current task refused
        r = _ok(lc({"kind": "task", "ids": [f"{TAG}_old", f"{TAG}_fresh"], "reason": "mock resident request from September"}))
        assert r["closed"] == 1 and r["refused"][0]["id"] == f"{TAG}_fresh"
        t = await db.staff_tasks.find_one({"task_id": f"{TAG}_old"}, {"_id": 0})
        assert t["status"] == "skipped" and "Legacy record closed after review" in t["notes"]
        assert await db.receipts.count_documents({"related_object_id": f"{TAG}_old", "action_type": "task_cancelled"}) == 1
    finally:
        await db.users.delete_many({"email": {"$regex": f"^{TAG}_"}})
        await db.alerts.delete_many({"_tag": TAG})
        await db.staff_tasks.delete_many({"_tag": TAG})
        await db.sim_runs.delete_many({"_tag": TAG})
        await db.receipts.delete_many({"related_object_id": {"$regex": f"^{TAG}_"}})


@pytest.mark.skipif(not _backend_up(), reason="backend not running")
def test_views_counts_and_audited_legacy_close():
    asyncio.run(_run())
