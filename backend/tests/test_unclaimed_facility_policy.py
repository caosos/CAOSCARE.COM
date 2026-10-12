"""careops-alerts-facility-policy-isolation-001: the nursing-unclaimed step of
the escalation tick uses each request's own facility rule (the same lookup
alerts use), the 600 s default only when that facility has no rule, and a
disabled facility rule stops only that facility. One facility's rule never
reaches another facility's (or an unscoped) request.
In-process, DB-direct; refuses to run against the live DB.
"""
import asyncio
import os
import sys
import uuid
from datetime import datetime, timedelta

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if os.environ.get("DB_NAME") in ("caoscare", "", None):
    pytest.skip("writes request records; point DB_NAME at a scratch database", allow_module_level=True)

from deps import db  # noqa: E402
from models import EscalationRule  # noqa: E402
from routes.escalation_tick import run_tick  # noqa: E402
from routes.resident_requests import ResidentRequestInput, create_resident_request  # noqa: E402

TAG = f"ufp_{uuid.uuid4().hex[:8]}"
FA, FB, FOFF = f"{TAG}_fa", f"{TAG}_fb", f"{TAG}_off"
DEFAULT = EscalationRule().nursing_unclaimed_seconds   # 600


async def _new(key, fac):
    r = await create_resident_request(ResidentRequestInput(category="nursing", room=f"{TAG}-{key}",
                                                           summary="Please help me", priority="high"))
    if fac:   # requests carry no facility today; a facility-scoped one is modelled by the field the tick reads
        await db.staff_tasks.update_one({"task_id": r["task_id"]}, {"$set": {"facility_id": fac}})
    return r["task_id"]


async def _flagged(tid):
    return bool((await db.staff_tasks.find_one({"task_id": tid})).get("unclaimed_escalated_at"))


async def _scenario():
    rules = [{"facility_id": FA, "nursing_unclaimed_seconds": 120},
             {"facility_id": FB, "nursing_unclaimed_seconds": 1200},
             {"facility_id": FOFF, "nursing_unclaimed_seconds": 60, "enabled": False}]
    await db.escalation_rules.insert_many([EscalationRule(**r).model_dump() for r in rules])
    try:
        a, b, off, none = (await _new("A", FA), await _new("B", FB), await _new("OFF", FOFF), await _new("N", None))
        t0 = datetime.fromisoformat((await db.staff_tasks.find_one({"task_id": none}))["created_at"])

        await run_tick(now=t0 + timedelta(seconds=300))
        assert await _flagged(a), "facility A's own 120 s rule"
        assert not await _flagged(b), "facility A's rule leaked onto facility B"
        assert not await _flagged(none), "a facility rule leaked onto a request with no facility (default 600 s)"
        assert not await _flagged(off)

        await run_tick(now=t0 + timedelta(seconds=DEFAULT + 30))
        assert await _flagged(none) and not await _flagged(b)
        await run_tick(now=t0 + timedelta(seconds=1300))
        assert await _flagged(b)
        assert not await _flagged(off), "a disabled facility rule must stop only that facility"

        for tid, auth in ((a, FA), (b, FB), (none, "default")):
            rs = await db.receipts.find({"related_object_id": tid, "action_type": "task_unclaimed_escalated"}).to_list(5)
            assert len(rs) == 1 and rs[0]["authority"] == f"escalation_rule:{auth}:nursing_unclaimed", (tid, rs)
    finally:
        await db.escalation_rules.delete_many({"facility_id": {"$regex": f"^{TAG}_"}})
        tids = [x["task_id"] for x in await db.staff_tasks.find({"room": {"$regex": f"^{TAG}-"}}, {"task_id": 1}).to_list(20)]
        await db.staff_tasks.delete_many({"task_id": {"$in": tids}})
        await db.receipts.delete_many({"related_object_id": {"$in": tids}})
        await db.notifications.delete_many({"related_object_id": {"$in": tids}})


def test_unclaimed_step_uses_each_facilitys_own_rule():
    asyncio.get_event_loop().run_until_complete(_scenario())
