"""Voice-context transportation entry points - resolve 'my request' by
resident_id/room/conversation_session_id (what a live Aria turn actually
has), not a task_id. Split out of transportation.py to keep both under the
300-line cap; delegates to the task_id-based endpoints there for the actual
change/cancel logic so there is exactly one booking/release code path.
"""
from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from deps import db
from routes.transportation import (
    OPEN_TASK_STATUSES, TransportChangeInput, change_transport_request, cancel_transport_request,
)

router = APIRouter(prefix="/transportation", tags=["transportation-voice-context"])


async def _find_open_request(resident_id: Optional[str], room: Optional[str], conversation_session_id: Optional[str]) -> dict:
    """Resolves 'my most recent open transportation request' the same way
    Aria resolves status lookups - by resident_id, then room, then session
    - since a live voice turn has that context, not an internal task_id."""
    q: dict = {"category": "transportation", "status": {"$in": OPEN_TASK_STATUSES}}
    if resident_id:
        q["resident_id"] = resident_id
    elif room:
        q["room"] = room
    elif conversation_session_id:
        q["conversation_session_id"] = conversation_session_id
    else:
        raise HTTPException(status_code=400, detail="resident_id, room, or conversation_session_id required")
    task = await db.staff_tasks.find_one(q, {"_id": 0}, sort=[("created_at", -1)])
    if not task:
        raise HTTPException(status_code=404, detail="No open transportation request found")
    return task


class TransportChangeByContextInput(TransportChangeInput):
    resident_id: Optional[str] = None
    room: Optional[str] = None
    conversation_session_id: Optional[str] = None


@router.post("/request/change-mine")
async def change_my_transport_request(data: TransportChangeByContextInput):
    """Voice-path entry point - resolves the request by resident/room/
    session context (what Aria actually has) instead of a task_id, then
    delegates to the same change logic /request/{task_id}/change uses."""
    existing = await _find_open_request(data.resident_id, data.room, data.conversation_session_id)
    return await change_transport_request(existing["task_id"], TransportChangeInput(**data.model_dump(exclude={"resident_id", "room", "conversation_session_id"})))


class TransportCancelByContextInput(BaseModel):
    resident_id: Optional[str] = None
    room: Optional[str] = None
    conversation_session_id: Optional[str] = None


@router.post("/request/cancel-mine")
async def cancel_my_transport_request(data: TransportCancelByContextInput):
    existing = await _find_open_request(data.resident_id, data.room, data.conversation_session_id)
    return await cancel_transport_request(existing["task_id"])


@router.get("/request/status")
async def transport_request_status(
    resident_id: Optional[str] = None, room: Optional[str] = None, conversation_session_id: Optional[str] = None,
):
    q: dict = {"category": "transportation", "source": {"$in": ["aria_voice", "kiosk_button"]}}
    if resident_id:
        q["resident_id"] = resident_id
    elif room:
        q["room"] = room
    elif conversation_session_id:
        q["conversation_session_id"] = conversation_session_id
    else:
        raise HTTPException(status_code=400, detail="resident_id, room, or conversation_session_id required")
    task = await db.staff_tasks.find_one(q, {"_id": 0}, sort=[("created_at", -1)])
    if not task:
        return {"found": False}
    slot = None
    if task.get("transport_run_id"):
        run = await db.transport_runs.find_one({"run_id": task["transport_run_id"]}, {"_id": 0, "depart_time": 1, "return_time": 1})
        slot = {"start_time": run["depart_time"], "end_time": run.get("return_time")} if run else None
    elif task.get("transport_slot_id"):
        slot = await db.transport_slots.find_one({"slot_id": task["transport_slot_id"]}, {"_id": 0, "start_time": 1, "end_time": 1})
    return {
        "found": True,
        "status": task["status"],
        "booked": bool(task.get("transport_run_id") or task.get("transport_slot_id")),
        "requested_for_date": task.get("requested_for_date"),
        "requested_for_time_label": task.get("requested_for_time_label"),
        "slot": slot,
        "re_request_count": task.get("re_request_count", 0),
    }
