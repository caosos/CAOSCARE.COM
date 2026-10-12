"""A call asked for from a voice conversation (resident Aria core plan step 4).

`POST /telephony/room-call-request` checks the target against the existing rules — the front desk, or a
family contact approved for resident calls (allow_calls, phone on file) — and answers truthfully. There is
no outbound dialing path from a room conversation yet (the phone code only transfers calls already in
progress, and Asterisk is not connected), so a valid request is refused with "calling isn't set up here
yet" and a receipt; no CallSession is created, so nothing can read as requested/ringing/connected.
The voice tool is offered only when CAOSCARE_CALL_TOOL is on (default off).

Callers: a live resident session (lease-grounded, like /research), or the signed-in owner.
"""
import os
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from deps import db
from routes.receipts import create_receipt

router = APIRouter(prefix="/telephony", tags=["telephony"])


def call_tool_enabled() -> bool:
    return (os.environ.get("CAOSCARE_CALL_TOOL", "") or "").strip().lower() in ("1", "true", "yes", "on")


def outbound_calling_ready() -> bool:
    """Whether a room conversation can actually place a call. Always False until an outbound originate path
    exists; kept as one function so the tool's wording follows it."""
    return False


CALL_CONTACT_TOOL = {
    "type": "function", "name": "call_contact",
    "description": ("Ask the phone system to call the front desk or one of the resident's family contacts who is approved "
                    "for calls. Speak only from the result: if it says calling is not set up, say so plainly and offer "
                    "request_staff_help instead. Never say you are calling, it is ringing, or someone answered unless "
                    "the result says so."),
    "parameters": {"type": "object", "properties": {
        "target": {"type": "string", "description": "\"front desk\" or the family member's name as the resident said it"}},
        "required": ["target"]},
}


class RoomCallRequest(BaseModel):
    target: str = Field(min_length=1, max_length=80)
    resident_id: Optional[str] = Field(default=None, max_length=64)
    session_id: Optional[str] = Field(default=None, max_length=128)


async def _caller(request: Request, body: RoomCallRequest) -> dict:
    from routes.session_grounding import find_live_session
    if body.resident_id and body.session_id:
        live = await find_live_session(body.resident_id, body.session_id)
        if live:
            return {"kind": "resident", "resident_id": body.resident_id, "room": live.get("room")}
    from deps import get_current_user
    try:
        user = await get_current_user(request)
    except HTTPException:
        user = None
    if user and user.get("role") == "owner":
        return {"kind": "owner", "resident_id": None, "room": None, "user_id": user["user_id"]}
    raise HTTPException(status_code=403, detail="A call can only be asked for from a live conversation")


async def _resolve_target(target: str, resident_id: Optional[str]) -> dict:
    t = " ".join(target.lower().split())
    if t in ("front desk", "the front desk", "frontdesk", "reception", "front office"):
        return {"type": "front_desk", "label": "the front desk"}
    if not resident_id:
        return {"type": "unknown", "label": target}
    from routes.phone_aria_tools import approved_family_contacts
    for c in await approved_family_contacts(resident_id):
        name = (c.get("name") or "").lower()
        if t == name or t in name.split() or t == (c.get("relationship") or "").lower():
            return {"type": "family", "label": c.get("name"), "contact_id": c["contact_id"]}
    return {"type": "not_approved", "label": target}


@router.post("/room-call-request")
async def room_call_request(body: RoomCallRequest, request: Request):
    caller = await _caller(request, body)
    tgt = await _resolve_target(body.target, caller["resident_id"])
    if tgt["type"] in ("not_approved", "unknown"):
        message = (f"I can't call {body.target}: they aren't on the list of contacts approved for calls. "
                   "Staff can add or approve a contact.")
        outcome = "not_approved"
    elif not outbound_calling_ready():
        message = (f"Calling isn't set up here yet, so I can't call {tgt['label']}. "
                   "I can send the staff a request instead.")
        outcome = "not_configured"
    else:                                                    # unreachable until an outbound path exists
        message, outcome = "Calling isn't set up here yet.", "not_configured"
    receipt = await create_receipt(
        action_type=f"call.room_request.{outcome}", related_object_type="call_request",
        related_object_id=tgt.get("contact_id") or tgt["type"], source="aria_voice" if caller["kind"] == "resident" else "staff",
        resident_id=caller["resident_id"], room=caller["room"], conversation_session_id=body.session_id,
        status="failed", result=message, failure_reason=outcome,
        provenance={"actor_type": "real-human",
                    "identity_basis": "unverified_room_claim" if caller["kind"] == "resident" else "authenticated",
                    "after_state": {"target": body.target, "resolved": tgt}},
    )
    return {"ok": False, "outcome": outcome, "message": message, "target": tgt, "receipt_id": receipt["receipt_id"]}
