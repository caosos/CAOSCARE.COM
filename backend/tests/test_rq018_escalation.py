"""RQ-018: escalation.py/escalation_tick.run_tick is the sole escalation
authority. Unanswered alerts escalate once per level with an appended receipt;
acknowledged, resolved and stale (> STALE_ALERT_HOURS) alerts do not; the
live feed only reads; concurrent ticks escalate once; the schedule can be
disabled. In-process, DB-direct; refuses to run against the live DB.
"""
import asyncio
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

if os.environ.get("DB_NAME") in ("caoscare", "", None):
    pytest.skip("writes alert records; point DB_NAME at a scratch database",
                allow_module_level=True)

from deps import db  # noqa: E402
from routes.alerts import alerts_feed  # noqa: E402
from routes.escalation_tick import auto_interval_seconds, run_tick  # noqa: E402
from routes.ops_overview_util import STALE_ALERT_HOURS  # noqa: E402

TAG = f"rq018_{uuid.uuid4().hex[:8]}"
T0 = datetime.now(timezone.utc)


def run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


def _alert(name, age_s, **extra):
    return {"alert_id": f"{TAG}_{name}", "room": f"{TAG}-R", "severity": "assist",
            "status": "active", "escalation_level": 0,
            "created_at": (T0 - timedelta(seconds=age_s)).isoformat(), **extra}


async def _get(name):
    return await db.alerts.find_one({"alert_id": f"{TAG}_{name}"}, {"_id": 0})


async def _receipts(name):
    return await db.receipts.find(
        {"related_object_id": f"{TAG}_{name}", "action_type": "alert_escalated"},
        {"_id": 0}).sort("created_at", 1).to_list(10)


async def _cleanup():
    await db.alerts.delete_many({"alert_id": {"$regex": f"^{TAG}_"}})
    await db.receipts.delete_many({"related_object_id": {"$regex": f"^{TAG}_"}})


def test_escalates_once_per_level_with_receipts():
    async def go():
        await _cleanup()
        await db.alerts.insert_one(_alert("a", 100))
        await run_tick(T0)
        a = await _get("a")
        assert a["escalation_level"] == 2 and a["status"] == "active"
        assert (await run_tick(T0))["escalated_to_2"] == 0  # idempotent
        rs = await _receipts("a")
        assert len(rs) == 1
        r = rs[0]
        assert r["actor_id"] == "system:escalation" and r["actor_type"] == "system"
        assert r["before_state"] == {"escalation_level": 0}
        assert r["after_state"]["escalation_level"] == 2
        assert r["after_state"]["thresholds"] == {"level_2_seconds": 90, "level_3_seconds": 150}
        assert r["authority"].startswith("escalation_rule:")
        # 60s later: reaches level 3, a NEW receipt, the first is untouched
        await run_tick(T0 + timedelta(seconds=60))
        a = await _get("a")
        assert a["escalation_level"] == 3
        rs2 = await _receipts("a")
        assert len(rs2) == 2 and rs2[0] == rs[0]
        assert rs2[1]["before_state"] == {"escalation_level": 2}
        await run_tick(T0 + timedelta(seconds=600))
        assert len(await _receipts("a")) == 2  # level 3 is final
        await _cleanup()
    run(go())


def test_acknowledged_resolved_and_stale_are_not_escalated():
    async def go():
        await _cleanup()
        old = STALE_ALERT_HOURS * 3600 + 3600
        await db.alerts.insert_many([
            _alert("ack", 500, status="acknowledged", acknowledged_at=T0.isoformat()),
            _alert("ackactive", 500, acknowledged_at=T0.isoformat()),
            _alert("res", 500, status="resolved", resolved_at=T0.isoformat()),
            _alert("stale", old),
            _alert("fresh", 10),
        ])
        out = await run_tick(T0)
        assert out["stale_skipped"] >= 1
        for n in ("ack", "ackactive", "res", "stale", "fresh"):
            assert (await _get(n))["escalation_level"] == 0, n
            assert await _receipts(n) == [], n
        await _cleanup()
    run(go())


def test_feed_is_read_only():
    async def go():
        await _cleanup()
        await db.alerts.insert_one(_alert("feed", 1000))  # old enough for any threshold
        items = await alerts_feed(user={"name": "t", "role": "admin"})
        mine = [i for i in items if i["alert_id"] == f"{TAG}_feed"]
        assert mine and mine[0]["escalation_level"] == 0
        assert (await _get("feed"))["escalation_level"] == 0
        assert await _receipts("feed") == []
        await run_tick(T0)
        items = await alerts_feed(user={"name": "t", "role": "admin"})
        assert [i for i in items if i["alert_id"] == f"{TAG}_feed"][0]["escalation_level"] == 3
        await _cleanup()
    run(go())


def test_concurrent_ticks_escalate_once():
    async def go():
        await _cleanup()
        await db.alerts.insert_one(_alert("race", 100))
        await asyncio.gather(*[run_tick(T0) for _ in range(6)])
        assert (await _get("race"))["escalation_level"] == 2
        assert len(await _receipts("race")) == 1
        await _cleanup()
    run(go())


def test_schedule_can_be_disabled(monkeypatch):
    monkeypatch.setenv("CAOSCARE_ESCALATION_AUTO", "0")
    assert auto_interval_seconds() is None
    monkeypatch.setenv("CAOSCARE_ESCALATION_AUTO", "1")
    monkeypatch.setenv("CAOSCARE_ESCALATION_INTERVAL", "45")
    assert auto_interval_seconds() == 45
    monkeypatch.delenv("CAOSCARE_ESCALATION_INTERVAL")
    assert auto_interval_seconds() == 30


def test_escalation_module_does_not_import_simulator():
    path = os.path.join(os.path.dirname(__file__), "..", "routes", "escalation_tick.py")
    imports = [l for l in open(path) if l.startswith(("import ", "from "))]
    assert not any("simulat" in l for l in imports)
