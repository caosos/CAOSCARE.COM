"""careops-housekeeping-supplies-linen-001: a supply/linen request carries the
items and quantities the resident asked for, from Aria's tool through the
request, the resident's view and Aria's status; bad items are refused; the
housekeeping lifecycle fulfils it; other departments are refused. There is no
inventory/stock source, so nothing claims stock. In-process; scratch DB only.
"""
import asyncio
import os
import sys
import uuid

import pytest
from pydantic import ValidationError

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if os.environ.get("DB_NAME") in ("caoscare", "", None):
    pytest.skip("writes request records; point DB_NAME at a scratch database", allow_module_level=True)

from fastapi import HTTPException  # noqa: E402
from deps import db  # noqa: E402
from routes import task_actions  # noqa: E402
from routes.actor_context import actor_from_user  # noqa: E402
from routes.realtime_tools import _build_tools  # noqa: E402
from routes.resident_requests import ResidentRequestInput, create_resident_request, resident_request_status  # noqa: E402

TAG = f"hksup_{uuid.uuid4().hex[:8]}"


def run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


def test_tool_schema_offers_items():
    tool = next(t for t in asyncio.get_event_loop().run_until_complete(_build_tools()) if t.get("name") == "request_staff_help")
    items = tool["parameters"]["properties"]["items"]
    assert items["type"] == "array" and set(items["items"]["required"]) == {"item", "quantity"}
    assert "sent only if" in tool["description"]


def test_bad_items_are_refused():
    with pytest.raises(ValidationError):
        ResidentRequestInput(category="housekeeping", summary="x", items=[{"item": "towels", "quantity": 0}])
    with pytest.raises(ValidationError):
        ResidentRequestInput(category="housekeeping", summary="x", items=[{"item": "", "quantity": 1}])
    with pytest.raises(ValidationError):
        ResidentRequestInput(category="housekeeping", summary="x", items=[{"item": "t", "quantity": 1}] * 11)


async def _scenario():
    hk = {"user_id": f"{TAG}_hk", "name": "Housekeeper", "role": "staff", "department": "housekeeping"}
    nurse = {"user_id": f"{TAG}_nurse", "name": "Nurse", "role": "staff", "department": "nursing"}
    await db.users.insert_many([dict(u) for u in (hk, nurse)])
    room = f"{TAG}-R"
    try:
        r = await create_resident_request(ResidentRequestInput(
            category="housekeeping", room=room, summary="Two towels and a blanket",
            resident_words="Could I get two extra towels and a warm blanket?",
            items=[{"item": "towels", "quantity": 2}, {"item": "warm blanket", "quantity": 1}]))
        tid = r["task_id"]
        doc = await db.staff_tasks.find_one({"task_id": tid})
        assert doc["items"] == [{"item": "towels", "quantity": 2}, {"item": "warm blanket", "quantity": 1}]
        assert doc["visibility_role"] == "housekeeping"
        s = await resident_request_status(room=room)
        assert s["items"] == doc["items"]

        with pytest.raises(HTTPException) as e:
            await task_actions.complete(tid, "x", actor_from_user(nurse), nurse)
        assert e.value.status_code == 403
        await task_actions.assign(tid, hk["user_id"], actor_from_user(hk), hk)
        s = await resident_request_status(room=room)
        assert "2 × towels" in s["spoken"] and "1 × warm blanket" in s["spoken"] and "stock" not in s["spoken"].lower()
        # Claimed, then started, then completed (#168: claim is not completion).
        await task_actions.start(tid, actor_from_user(hk), hk)
        await task_actions.complete(tid, "Delivered 2 towels and a blanket", actor_from_user(hk), hk)
        chain = await db.receipts.find({"related_object_id": tid}).sort("created_at", 1).to_list(20)
        assert [c["action_type"] for c in chain] == ["resident_request_created", "task_assigned",
                                                     "task_in_progress", "task_completed"]
    finally:
        await db.users.delete_many({"user_id": {"$regex": f"^{TAG}_"}})
        tids = [x["task_id"] for x in await db.staff_tasks.find({"room": room}, {"task_id": 1}).to_list(10)]
        await db.staff_tasks.delete_many({"task_id": {"$in": tids}})
        await db.receipts.delete_many({"related_object_id": {"$in": tids}})
        await db.notifications.delete_many({"related_object_id": {"$in": tids}})


def test_supply_request_items_end_to_end():
    run(_scenario())
