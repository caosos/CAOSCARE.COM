"""careops-alerts-loop-death-receipt-001: when the escalation loop ends
unexpectedly while the backend keeps running, one `escalation_schedule_stopped`
receipt is written (system actor, schedule authority, before/after, error,
parent); a repeat adds nothing; the intentional shutdown cancel writes nothing;
the next good tick records the recovery chained to the stop. No escalation,
SMS or call is claimed. In-process, DB-direct; refuses to run against the live DB.
"""
import asyncio
import os
import sys
from datetime import datetime, timezone

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if os.environ.get("DB_NAME") in ("caoscare", "", None):
    pytest.skip("writes receipt records; point DB_NAME at a scratch database", allow_module_level=True)

from deps import db  # noqa: E402
from routes import escalation_schedule as et  # noqa: E402

T0 = datetime.now(timezone.utc).isoformat()


async def _schedule_receipts():
    return await db.receipts.find({"related_object_type": "escalation_schedule", "created_at": {"$gte": T0}},
                                  {"_id": 0}).sort("created_at", 1).to_list(20)


async def _settle():
    for _ in range(20):
        await asyncio.sleep(0.05)


async def _scenario(monkeypatch):
    monkeypatch.setenv("CAOSCARE_ESCALATION_AUTO", "1")
    et._health_state.clear()
    et._health_state.update(state="healthy", receipt_id=None)   # a running schedule
    real_loop = et.run_escalation_loop
    notes_before = await db.notifications.count_documents({})
    async def sleeper(interval):
        await asyncio.sleep(3600)
    try:
        # 2. the loop dies while the process lives -> one stopped receipt
        async def dies(interval):
            raise MemoryError("loop crashed (synthetic)")
        monkeypatch.setattr(et, "run_escalation_loop", dies)
        await et.start_schedule()
        await _settle()
        rs = await _schedule_receipts()
        assert len(rs) == 1, rs
        s = rs[0]
        assert s["action_type"] == "escalation_schedule_stopped" and s["status"] == "failed"
        assert s["actor_id"] == "system:escalation" and s["actor_type"] == "system"
        assert s["authority"] == "escalation_schedule"
        assert s["before_state"] == {"tick": "healthy"} and s["after_state"]["tick"] == "stopped"
        assert "loop crashed" in s["failure_reason"] and s["result_label"] == "failed"
        assert s["next_state"] == "not_escalating_until_restart"
        assert et.escalation_status()["state"] == "stopped"

        # 3. it dies again (no recovery in between) -> nothing new
        await et.start_schedule()
        await _settle()
        assert len(await _schedule_receipts()) == 1

        # 4. an unrequested cancel is also an unexpected stop, but still one receipt for the state
        monkeypatch.setattr(et, "run_escalation_loop", sleeper)
        task = await et.start_schedule()
        await asyncio.sleep(0.05)
        task.cancel()
        await _settle()
        assert len(await _schedule_receipts()) == 1

        # 5. recovery: a good tick chains to the stop
        monkeypatch.setattr(et, "run_escalation_loop", real_loop)
        await et.tick_once()
        rs = await _schedule_receipts()
        assert len(rs) == 2 and rs[0] == s
        r = rs[1]
        assert r["action_type"] == "escalation_tick_recovered" and r["parent_receipt_id"] == s["receipt_id"]
        assert r["before_state"]["tick"] == "stopped"
        assert await db.notifications.count_documents({}) == notes_before

        # 1. intentional shutdown: the lifespan stops a healthy loop -> no receipt
        await et.start_schedule()
        await asyncio.sleep(0.05)
        await et.stop_schedule()
        await _settle()
        assert len(await _schedule_receipts()) == 2, "an intentional shutdown is not a failure"
    finally:
        await et.stop_schedule() if hasattr(et, "stop_schedule") else None
        et._schedule.update(task=None, interval=None, last_tick_at=None)
        await db.receipts.delete_many({"related_object_type": "escalation_schedule", "created_at": {"$gte": T0}})


def test_unexpected_loop_end_is_receipted_once_and_shutdown_is_not(monkeypatch):
    asyncio.get_event_loop().run_until_complete(_scenario(monkeypatch))
