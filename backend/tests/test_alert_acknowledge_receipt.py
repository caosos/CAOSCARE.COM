"""careops-alerts-canonical-state-001: acknowledging a resident-assistance alert
is a receipted, history-logged, idempotent transition (it stops escalation and
marks the nursing dispatch delivered, so it must carry provenance).
In-process, DB-direct; refuses to run against the live DB.
"""
import asyncio
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if os.environ.get("DB_NAME") in ("caoscare", "", None):
    pytest.skip("writes alert records; point DB_NAME at a scratch database", allow_module_level=True)

from deps import db  # noqa: E402
from routes.alerts import acknowledge  # noqa: E402
from routes.escalation_tick import run_tick  # noqa: E402

TAG = f"ack_{uuid.uuid4().hex[:8]}"
T0 = datetime.now(timezone.utc)
NURSE = {"user_id": f"{TAG}_nurse", "name": f"{TAG} Nurse", "role": "staff", "department": "nursing"}


def run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


async def _seed(name, **extra):
    doc = {"alert_id": f"{TAG}_{name}", "room": f"{TAG}-R", "resident_id": f"{TAG}_res", "severity": "assist",
           "status": "active", "escalation_level": 0, "event_log": [],
           "created_at": (T0 - timedelta(seconds=30)).isoformat(), **extra}
    await db.alerts.insert_one(doc)
    return doc["alert_id"]


async def _acks(aid):
    return await db.receipts.find({"related_object_id": aid, "action_type": "alert_acknowledged"},
                                  {"_id": 0}).to_list(20)


async def _cleanup():
    await db.alerts.delete_many({"alert_id": {"$regex": f"^{TAG}_"}})
    await db.receipts.delete_many({"related_object_id": {"$regex": f"^{TAG}_"}})


def test_acknowledge_is_receipted_logged_and_idempotent():
    async def go():
        await _cleanup()
        aid = await _seed("a")
        doc = await acknowledge(aid, user=NURSE)
        assert doc["status"] == "acknowledged" and doc["acknowledged_by"] == NURSE["name"]
        recs = await _acks(aid)
        assert len(recs) == 1, recs
        r = recs[0]
        assert r["actor_id"] == NURSE["user_id"] and r["actor_type"] == "real-human"
        assert r["before_state"]["status"] == "active" and r["after_state"]["status"] == "acknowledged"
        assert r["related_object_type"] == "alert" and r["resident_id"] == f"{TAG}_res"
        ev = [e for e in doc["event_log"] if e.get("field") == "status"]
        assert ev and ev[-1]["to"] == "acknowledged" and ev[-1]["receipt_id"] == r["receipt_id"]
        # repeat: refused, nothing new written
        with pytest.raises(HTTPException) as e:
            await acknowledge(aid, user=NURSE)
        assert e.value.status_code == 404 and len(await _acks(aid)) == 1
        # escalation stops after acknowledgement
        await db.alerts.update_one({"alert_id": aid}, {"$set": {"created_at": (T0 - timedelta(seconds=400)).isoformat()}})
        await run_tick(T0)
        assert (await db.alerts.find_one({"alert_id": aid}))["escalation_level"] == 0

        # concurrent acknowledgements: exactly one wins, one receipt, one history entry
        bid = await _seed("b")
        results = await asyncio.gather(*[acknowledge(bid, user={**NURSE, "user_id": f"{TAG}_n{i}", "name": f"N{i}"})
                                         for i in range(6)], return_exceptions=True)
        assert sum(1 for x in results if isinstance(x, dict)) == 1
        assert all(isinstance(x, HTTPException) and x.status_code == 404 for x in results if not isinstance(x, dict))
        assert len(await _acks(bid)) == 1
        b = await db.alerts.find_one({"alert_id": bid}, {"_id": 0})
        assert len([e for e in b["event_log"] if e.get("field") == "status"]) == 1

        # a legacy "escalated" row is acknowledged and receipted the same way
        cid = await _seed("c", status="escalated", escalation_level=3)
        await acknowledge(cid, user=NURSE)
        assert (await _acks(cid))[0]["before_state"]["status"] == "escalated"
        await _cleanup()
    run(go())
