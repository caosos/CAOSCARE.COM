"""careops-alerts-close-receipts-001: resolve and close are one status-guarded
terminal transition with exactly one alert_completed receipt (actor,
authority, before/after) and one linked history entry; repeats and concurrent
attempts have one winner; legacy `escalated` rows close too.
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
from models import AlertClose  # noqa: E402
from routes.alerts import acknowledge, close_alert, resolve  # noqa: E402

TAG = f"cls_{uuid.uuid4().hex[:8]}"
T0 = datetime.now(timezone.utc)
NURSE = {"user_id": f"{TAG}_nurse", "name": f"{TAG} Nurse", "role": "staff", "department": "nursing"}


def run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


async def _seed(name, **extra):
    doc = {"alert_id": f"{TAG}_{name}", "room": f"{TAG}-R", "resident_id": f"{TAG}_res", "severity": "assist",
           "status": "active", "escalation_level": 0, "event_log": [],
           "created_at": (T0 - timedelta(seconds=60)).isoformat(), **extra}
    await db.alerts.insert_one(doc)
    return doc["alert_id"]


async def _done(aid):
    return await db.receipts.find({"related_object_id": aid, "action_type": "alert_completed"}, {"_id": 0}).to_list(20)


async def _cleanup():
    await db.alerts.delete_many({"alert_id": {"$regex": f"^{TAG}_"}})
    await db.receipts.delete_many({"related_object_id": {"$regex": f"^{TAG}_"}})


def _status_events(doc):
    return [e for e in doc.get("event_log", []) if e.get("field") == "status" and e.get("to") == "resolved"]


def test_close_paths_are_one_receipted_terminal_transition():
    async def go():
        await _cleanup()
        body = AlertClose(outcome="resolved_no_action", close_notes="checked on resident")
        # close from active
        a = await _seed("a")
        doc = await close_alert(a, body, user=NURSE)
        recs = await _done(a)
        assert len(recs) == 1, recs
        r = recs[0]
        assert r["actor_id"] == NURSE["user_id"] and r["actor_type"] == "real-human" and r["authority"]
        assert r["before_state"]["status"] == "active" and r["after_state"]["status"] == "resolved"
        assert r["after_state"]["outcome"] == "resolved_no_action"
        ev = _status_events(doc)
        assert len(ev) == 1 and ev[0]["receipt_id"] == r["receipt_id"]
        first = await db.alerts.find_one({"alert_id": a}, {"_id": 0})
        # repeat close and a later resolve: refused, nothing rewritten
        for again in (close_alert(a, AlertClose(outcome="other", close_notes="again"), user={**NURSE, "name": "Other"}),
                      resolve(a, user=NURSE)):
            with pytest.raises(HTTPException) as e:
                await again
            assert e.value.status_code == 409
        after = await db.alerts.find_one({"alert_id": a}, {"_id": 0})
        assert after["resolved_at"] == first["resolved_at"] and after["resolved_by"] == first["resolved_by"]
        assert after["outcome"] == "resolved_no_action" and len(await _done(a)) == 1

        # resolve from acknowledged
        b = await _seed("b")
        await acknowledge(b, user=NURSE)
        doc = await resolve(b, user=NURSE)
        rb = await _done(b)
        assert len(rb) == 1 and rb[0]["before_state"]["status"] == "acknowledged" and len(_status_events(doc)) == 1

        # legacy escalated row closes too
        c = await _seed("c", status="escalated", escalation_level=3)
        await resolve(c, user=NURSE)
        assert (await _done(c))[0]["before_state"]["status"] == "escalated"

        # concurrent close: one winner, one receipt, one history entry
        d = await _seed("d")
        res = await asyncio.gather(*[close_alert(d, body, user={**NURSE, "user_id": f"{TAG}_n{i}", "name": f"N{i}"})
                                     for i in range(6)], return_exceptions=True)
        assert sum(1 for x in res if isinstance(x, dict)) == 1
        assert all(isinstance(x, HTTPException) and x.status_code == 409 for x in res if not isinstance(x, dict))
        assert len(await _done(d)) == 1 and len(_status_events(await db.alerts.find_one({"alert_id": d}))) == 1

        # unknown alert: 404
        with pytest.raises(HTTPException) as e:
            await resolve(f"{TAG}_missing", user=NURSE)
        assert e.value.status_code == 404
        await _cleanup()
    run(go())
