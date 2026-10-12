"""careops-housekeeping-inspection-001: an owner/admin inspects completed
Housekeeping work. Return-for-correction (reason required) reopens the SAME
request through the receipted reopen and records the inspection; the
housekeeper corrects and completes it; Pass records the inspection and leaves
it completed. Staff cannot inspect; open work cannot be inspected; one chain.
In-process; scratch DB only.
"""
import asyncio
import os
import sys
import uuid

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if os.environ.get("DB_NAME") in ("caoscare", "", None):
    pytest.skip("writes request records; point DB_NAME at a scratch database", allow_module_level=True)

from fastapi import HTTPException  # noqa: E402
from deps import db  # noqa: E402
from routes import task_actions  # noqa: E402
from routes.actor_context import actor_from_user  # noqa: E402
from routes.aria_request_status import request_status_view  # noqa: E402
from routes.resident_requests import ResidentRequestInput, create_resident_request  # noqa: E402
from routes.task_review import inspect  # noqa: E402

TAG = f"hkins_{uuid.uuid4().hex[:8]}"


def run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


async def _scenario():
    admin = {"user_id": f"{TAG}_admin", "name": "Admin", "role": "admin"}
    hk = {"user_id": f"{TAG}_hk", "name": "Housekeeper", "role": "staff", "department": "housekeeping"}
    await db.users.insert_many([dict(u) for u in (admin, hk)])
    A, H = actor_from_user(admin), actor_from_user(hk)
    try:
        r = await create_resident_request(ResidentRequestInput(category="housekeeping", room=f"{TAG}-R",
                                                               summary="Clean the bathroom", resident_words="Please clean my bathroom"))
        tid = r["task_id"]
        with pytest.raises(HTTPException) as e:
            await inspect(tid, "pass", "", A, admin)
        assert e.value.status_code == 409                       # not completed yet
        await task_actions.assign(tid, hk["user_id"], H, hk)
        await task_actions.start(tid, H, hk)
        await task_actions.complete(tid, "Bathroom cleaned", H, hk)

        with pytest.raises(HTTPException) as e:
            await inspect(tid, "pass", "", H, hk)
        assert e.value.status_code == 403                       # staff cannot inspect
        with pytest.raises(HTTPException) as e:
            await inspect(tid, "return", "", A, admin)
        assert e.value.status_code == 422                       # a return needs a reason

        await inspect(tid, "return", "Mirror still streaked", A, admin)
        doc = await db.staff_tasks.find_one({"task_id": tid})
        assert doc["status"] == "pending" and doc["assigned_to"] == hk["user_id"] and doc["inspection_result"] == "returned"
        assert "Returned after inspection" in request_status_view(doc)["spoken"]

        await task_actions.start(tid, H, hk)
        await task_actions.complete(tid, "Mirror redone", H, hk)
        await inspect(tid, "pass", "Looks good", A, admin)
        await inspect(tid, "pass", "", A, admin)                 # again: nothing changes
        doc = await db.staff_tasks.find_one({"task_id": tid})
        assert doc["status"] == "completed" and doc["inspection_result"] == "passed"

        chain = await db.receipts.find({"related_object_id": tid}).sort("created_at", 1).to_list(30)
        kinds = [c["action_type"] for c in chain]
        assert kinds.count("task_inspected") == 1
        for want in ("task_completed", "task_reopened", "task_inspection_returned", "task_inspected"):
            assert want in kinds, kinds
        assert len({c.get("correlation_id") for c in chain if not c["action_type"].endswith("_refused")}) == 1
        assert {c["authority"] for c in chain if c["action_type"].startswith("task_inspect")} == {"admin_override:admin"}
        assert all(x.get("receipt_id") for x in doc["event_log"])
    finally:
        await db.users.delete_many({"user_id": {"$regex": f"^{TAG}_"}})
        tids = [x["task_id"] for x in await db.staff_tasks.find({"room": f"{TAG}-R"}, {"task_id": 1}).to_list(10)]
        await db.staff_tasks.delete_many({"task_id": {"$in": tids}})
        await db.receipts.delete_many({"related_object_id": {"$in": tids}})
        await db.notifications.delete_many({"related_object_id": {"$in": tids}})


def test_housekeeping_inspection():
    run(_scenario())
