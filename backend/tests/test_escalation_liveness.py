"""careops-alerts-loop-liveness-001: escalation switched off at startup, or a
loop that has stopped, never looks healthy. /api/health reports the
escalation schedule's state; switching it off is receipted once (system
actor, authority, before/after), not on every restart; the on-site alert
stays listed and acknowledgeable and no escalation or delivery is claimed.

The backend test gate starts its server with the escalation loop OFF
(CAOSCARE_ESCALATION_AUTO=0), which is exactly the disabled-at-startup case.

    TEST_API_BASE=http://127.0.0.1:8131 pytest tests/test_escalation_liveness.py -q
"""
import asyncio
import os
import sys
import uuid

import pytest
import requests

BASE_URL = os.environ.get("TEST_API_BASE", os.environ.get("REACT_APP_BACKEND_URL", "http://127.0.0.1:8000")).rstrip("/")
API = f"{BASE_URL}/api"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TAG = f"live_{uuid.uuid4().hex[:8]}"


def _health():
    try:
        r = requests.get(f"{API}/health", timeout=3)
        return r.json() if r.ok else None
    except Exception:
        return None


async def _scenario(monkeypatch):
    from motor.motor_asyncio import AsyncIOMotorClient
    from routes import escalation_schedule as escalation_tick
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]

    # the running server: disabled at startup is reported, not "ok" by silence
    h = _health()
    assert h.get("escalation", {}).get("state") == "disabled", h
    q = {"related_object_type": "escalation_schedule", "action_type": "escalation_schedule_disabled"}
    rs = await db.receipts.find(q, {"_id": 0}).to_list(10)
    assert len(rs) == 1, rs
    r = rs[0]
    assert r["actor_id"] == "system:escalation" and r["actor_type"] == "system"
    assert r["authority"] == "env:CAOSCARE_ESCALATION_AUTO"
    assert r["after_state"]["tick"] == "disabled" and r["before_state"]["tick"] in ("healthy", "failing")
    assert r["result_label"] == "verified"

    # a second start with it still off adds nothing (no receipt per restart)
    monkeypatch.setenv("CAOSCARE_ESCALATION_AUTO", "0")
    escalation_tick._health_state.clear()
    assert await escalation_tick.start_schedule() is None
    assert await db.receipts.count_documents(q) == 1
    assert escalation_tick.escalation_status()["state"] == "disabled"

    # a loop whose task has ended reads "stopped", never "running"
    async def done():
        return None
    escalation_tick._schedule.update(task=asyncio.ensure_future(done()), interval=30, last_tick_at=None)
    await asyncio.sleep(0)
    assert escalation_tick.escalation_status()["state"] == "stopped"
    escalation_tick._schedule.update(task=None, interval=None, last_tick_at=None)

    # the on-site alert is unaffected: listed and acknowledgeable over HTTP
    from models import uid, now_utc
    import bcrypt
    pw = "live-pw-12345678"
    await db.users.insert_one({"user_id": uid("user"), "email": f"{TAG}_n@example.com", "name": f"{TAG} N",
                               "role": "staff", "department": "nursing", "auth_provider": "jwt",
                               "created_at": now_utc().isoformat(),
                               "password_hash": bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()})
    aid = f"{TAG}_alert"
    await db.alerts.insert_one({"alert_id": aid, "room": f"{TAG}-R", "severity": "assist", "status": "active",
                                "escalation_level": 0, "event_log": [], "created_at": now_utc().isoformat()})
    try:
        tok = requests.post(f"{API}/auth/login", json={"email": f"{TAG}_n@example.com", "password": pw}, timeout=5).json()["token"]
        H = {"Authorization": f"Bearer {tok}"}
        feed = requests.get(f"{API}/alerts/feed", headers=H, timeout=5).json()
        items = feed if isinstance(feed, list) else feed.get("alerts", feed.get("items", []))
        assert aid in {a.get("alert_id") for a in items}
        assert requests.post(f"{API}/alerts/{aid}/acknowledge", headers=H, timeout=5).status_code == 200
        a = await db.alerts.find_one({"alert_id": aid})
        assert a["status"] == "acknowledged" and not a.get("escalation_level")
        assert await db.receipts.count_documents({"related_object_id": aid, "action_type": {"$regex": "escalated|sms|call"}}) == 0
    finally:
        await db.users.delete_many({"email": {"$regex": f"^{TAG}_"}})
        await db.alerts.delete_many({"alert_id": {"$regex": f"^{TAG}_"}})
        await db.receipts.delete_many({"related_object_id": {"$regex": f"^{TAG}_"}})


def test_disabled_or_stopped_escalation_never_looks_healthy(monkeypatch):
    if os.environ.get("DB_NAME") in ("caoscare", "", None):
        pytest.skip("point DB_NAME at a scratch database")
    if _health() is None:
        pytest.skip(f"backend not reachable at {API}")
    asyncio.new_event_loop().run_until_complete(_scenario(monkeypatch))
