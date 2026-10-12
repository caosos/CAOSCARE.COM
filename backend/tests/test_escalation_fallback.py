"""careops-alerts-fallback-contract-001, part (a): when the escalation tick
fails, the failure is receipted once (system actor, schedule authority,
before/after, error) instead of only logged; repeated failures add nothing;
the first good tick after it records the recovery, chained to the failure.
Throughout, the on-site alert stays active, visible and acknowledgeable, and
no external delivery is recorded or claimed.
In-process, DB-direct; refuses to run against the live DB.
"""
import asyncio
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if os.environ.get("DB_NAME") in ("caoscare", "", None):
    pytest.skip("writes alert/receipt records; point DB_NAME at a scratch database", allow_module_level=True)

from deps import db  # noqa: E402
from routes import escalation_tick  # noqa: E402
from routes.alerts import acknowledge, alerts_feed  # noqa: E402

TAG = f"efb_{uuid.uuid4().hex[:8]}"
NURSE = {"user_id": f"{TAG}_nurse", "name": f"{TAG} Nurse", "role": "staff", "department": "nursing"}


async def _health():
    return await db.receipts.find({"related_object_type": "escalation_schedule",
                                   "action_type": {"$in": ["escalation_tick_failed", "escalation_tick_recovered"]},
                                   "created_at": {"$gte": T0}}, {"_id": 0}).sort("created_at", 1).to_list(20)


T0 = datetime.now(timezone.utc).isoformat()


async def _one_scheduled_tick():
    """One pass of the background schedule exactly as the server runs it."""
    task = asyncio.ensure_future(escalation_tick.run_escalation_loop(3600))
    await asyncio.sleep(0.3)
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


async def _scenario(monkeypatch):
    aid = f"{TAG}_alert"
    await db.alerts.insert_one({"alert_id": aid, "room": f"{TAG}-R", "severity": "assist", "status": "active",
                                "escalation_level": 0, "event_log": [],
                                "created_at": (datetime.now(timezone.utc) - timedelta(seconds=30)).isoformat()})
    real = escalation_tick.run_tick

    async def broken(now=None):
        raise RuntimeError("database unreachable (synthetic)")
    # a running schedule (the gate's own server starts with it switched off)
    escalation_tick._health_state.clear()
    escalation_tick._health_state.update(state="healthy", receipt_id=None)
    try:
        notes_before = await db.notifications.count_documents({})
        monkeypatch.setattr(escalation_tick, "run_tick", broken)
        for _ in range(3):                                   # repeated failures
            await _one_scheduled_tick()
        rs = await _health()
        assert len(rs) == 1, rs
        f = rs[0]
        assert f["action_type"] == "escalation_tick_failed" and f["status"] == "failed"
        assert f["actor_id"] == "system:escalation" and f["actor_type"] == "system"
        assert f["authority"] == "escalation_schedule"
        assert f["before_state"] == {"tick": "healthy"} and f["after_state"]["tick"] == "failing"
        assert "database unreachable" in f["failure_reason"]
        assert f["result_label"] == "failed"

        # the on-site alert is still listed and can be acknowledged while escalation is down
        feed = await alerts_feed(user={"user_id": "x", "role": "admin"})
        items = feed if isinstance(feed, list) else feed.get("alerts", feed.get("items", []))
        assert aid in {a.get("alert_id") for a in items}
        await acknowledge(aid, user=NURSE)
        assert (await db.alerts.find_one({"alert_id": aid}))["status"] == "acknowledged"
        assert await db.notifications.count_documents({}) == notes_before, "no external delivery while failing"

        monkeypatch.setattr(escalation_tick, "run_tick", real)
        await _one_scheduled_tick()
        await _one_scheduled_tick()                    # a second good tick adds nothing
        rs = await _health()
        assert len(rs) == 2, rs
        r = rs[1]
        assert r["action_type"] == "escalation_tick_recovered" and r["status"] == "completed"
        assert r["parent_receipt_id"] == f["receipt_id"]
        assert r["before_state"]["tick"] == "failing" and r["after_state"]["tick"] == "healthy"
        assert rs[0] == f, "the failure receipt is never rewritten"
    finally:
        await db.alerts.delete_many({"alert_id": {"$regex": f"^{TAG}_"}})
        await db.receipts.delete_many({"related_object_id": {"$regex": f"^{TAG}_"}})
        await db.receipts.delete_many({"related_object_type": "escalation_schedule", "created_at": {"$gte": T0}})


def test_tick_failure_is_receipted_once_and_recovery_chains(monkeypatch):
    asyncio.get_event_loop().run_until_complete(_scenario(monkeypatch))
