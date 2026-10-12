"""careops-nursing-unclaimed-escalation-001: the escalation tick flags a Nursing
request nobody has claimed past `nursing_unclaimed_seconds` exactly once, with a
receipt chained to its origin; the request stays open; repeated and concurrent
ticks do not flag it again; an assigned or closed request is not flagged; the
supervisor sees it in routing exceptions while unassigned; Aria's status says so.
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
    pytest.skip("writes request records; point DB_NAME at a scratch database", allow_module_level=True)

from fastapi import HTTPException  # noqa: E402
from deps import db  # noqa: E402
from models import EscalationRule  # noqa: E402
from routes import task_actions  # noqa: E402
from routes.actor_context import actor_from_user  # noqa: E402
from routes.aria_request_status import request_status_view  # noqa: E402
from routes.escalation_tick import run_tick  # noqa: E402
from routes.resident_requests import ResidentRequestInput, create_resident_request  # noqa: E402
from routes.routing_exceptions import routing_exceptions  # noqa: E402

TAG = f"nunc_{uuid.uuid4().hex[:8]}"
THRESH = EscalationRule().nursing_unclaimed_seconds


def run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


async def _new(room, words):
    r = await create_resident_request(ResidentRequestInput(category="nursing", room=room, summary=words,
                                                           resident_words=words, priority="high"))
    return r["task_id"]


async def _scenario():
    admin = {"user_id": f"{TAG}_admin", "name": "Admin", "role": "admin"}
    nurse = {"user_id": f"{TAG}_nurse", "name": "Nurse", "role": "staff", "department": "nursing"}
    maint = {"user_id": f"{TAG}_maint", "name": "Maint", "role": "staff", "department": "maintenance"}
    await db.users.insert_many([dict(u) for u in (admin, nurse, maint)])
    try:
        a = await _new(f"{TAG}-A", "I need help going to the bathroom")
        b = await _new(f"{TAG}-B", "Please help me back to bed")
        c = await _new(f"{TAG}-C", "My call light is not working well")
        task_b = await db.staff_tasks.find_one({"task_id": b})
        created = datetime.fromisoformat(task_b["created_at"])
        await task_actions.assign(b, nurse["user_id"], actor_from_user(nurse), nurse)         # claimed in time
        await task_actions.skip(c, "Resident changed mind", actor_from_user(nurse), nurse)    # closed

        early = await run_tick(now=created + timedelta(seconds=THRESH - 5))
        assert (await db.staff_tasks.find_one({"task_id": a})).get("unclaimed_escalated_at") is None
        late = created + timedelta(seconds=THRESH + 5)
        results = await asyncio.gather(run_tick(now=late), run_tick(now=late))         # concurrent ticks
        await run_tick(now=late + timedelta(minutes=5))                                 # repeated tick
        assert early["unclaimed_flagged"] == 0

        doc_a = await db.staff_tasks.find_one({"task_id": a})
        assert doc_a["unclaimed_escalated_at"] and doc_a["status"] == "pending" and doc_a["assigned_to"] is None
        rcpts = await db.receipts.find({"related_object_id": a, "action_type": "task_unclaimed_escalated"}).to_list(10)
        assert len(rcpts) == 1
        r = rcpts[0]
        assert r["actor_type"] == "system" and r["authority"].startswith("escalation_rule:")
        origin = await db.receipts.find_one({"related_object_id": a, "action_type": "resident_request_created"})
        assert r["correlation_id"] == origin["receipt_id"]
        assert [e for e in doc_a["event_log"] if e["field"] == "unclaimed_escalated"][0]["receipt_id"] == r["receipt_id"]
        for t in (b, c):
            assert not (await db.staff_tasks.find_one({"task_id": t})).get("unclaimed_escalated_at")
        assert sum(x["unclaimed_flagged"] for x in results) == 1

        assert "flagged to a supervisor" in request_status_view(doc_a)["spoken"]
        ex = await routing_exceptions(kind="unclaimed", user=admin)
        assert a in {i["task_id"] for i in ex["items"]}
        mine = await routing_exceptions(kind="unclaimed", user=maint)
        assert a not in {i["task_id"] for i in mine["items"]}

        await task_actions.assign(a, nurse["user_id"], actor_from_user(nurse), nurse)
        ex = await routing_exceptions(kind="unclaimed", user=admin)
        assert a not in {i["task_id"] for i in ex["items"]}
        await run_tick(now=late + timedelta(hours=1))
        assert await db.receipts.count_documents({"related_object_id": a, "action_type": "task_unclaimed_escalated"}) == 1
    finally:
        await db.users.delete_many({"user_id": {"$regex": f"^{TAG}_"}})
        tids = [x["task_id"] for x in await db.staff_tasks.find({"room": {"$regex": f"^{TAG}-"}}, {"task_id": 1}).to_list(20)]
        await db.staff_tasks.delete_many({"task_id": {"$in": tids}})
        await db.receipts.delete_many({"related_object_id": {"$in": tids}})
        await db.notifications.delete_many({"related_object_id": {"$in": tids}})


def test_unclaimed_nursing_request_is_flagged_once():
    run(_scenario())
