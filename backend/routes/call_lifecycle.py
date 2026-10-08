"""Call lifecycle - the one place a CallSession changes state.

States only move forward (see TRANSITIONS); a late or duplicate phone-system
event is ignored, never allowed to rewind a call. Every change is appended to
`history` (the call's own event log). Receipts record external effects only:
the attempt being placed, and its outcome (connected / unanswered / failed) -
each a new receipt, never an edit of an earlier one.
"""
import secrets
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

from deps import db, require_admin
from models import now_utc
from models_calls import CallSession
from routes.receipts import create_receipt

router = APIRouter(prefix="/telephony", tags=["telephony"])

TERMINAL_OUTCOMES = {"connected", "unanswered", "failed"}
TRANSITIONS = {
    "requested": {"dialing", "ringing", "connected", "unanswered", "failed", "ended"},
    "dialing": {"ringing", "connected", "unanswered", "failed", "ended"},
    "ringing": {"connected", "unanswered", "failed", "ended"},
    "connected": {"ended"},
    "unanswered": {"ended"},
    "failed": {"ended"},
    "ended": set(),
}


def _now() -> str:
    return now_utc().isoformat()


def new_dial_token() -> str:
    """8 digits, prefixed 77 by the dialplan - numeric so it matches an
    Asterisk extension pattern without letters."""
    return f"{secrets.randbelow(10**8):08d}"


async def create_call(kind: str, *, source: str = "caoscare", receipt_source: str = "system",
                      with_token: bool = False, **fields) -> dict:
    call = CallSession(kind=kind, dial_token=new_dial_token() if with_token else None, **fields)
    doc = call.model_dump()
    doc["created_at"] = doc["created_at"].isoformat()
    doc["history"] = [{"state": "requested", "at": doc["created_at"], "source": source, "detail": None}]
    await db.call_sessions.insert_one(dict(doc))
    doc.pop("_id", None)
    await create_receipt(
        action_type=f"call.{kind}.requested", related_object_type="call",
        related_object_id=doc["call_id"], source=receipt_source,
        resident_id=doc.get("resident_id"), room=doc.get("room"),
        conversation_session_id=doc.get("conversation_session_id"),
    )
    return doc


# Calls the dialplan starts on its own (no CAOSCare round-trip before
# dialing) carry a CAOS_CALL_ID with one of these prefixes; the record is
# created the first time the phone system reports on them.
DIALPLAN_PREFIX_KIND = {"aria-": "aria", "fd0-": "front_desk", "emg-": "emergency"}
KIND_LABEL = {"aria": "Aria", "front_desk": "the front desk", "emergency": "911"}


async def ensure_call(call_id: str, *, from_extension: Optional[str] = None) -> Optional[dict]:
    """Idempotently create the CallSession for a dialplan-started call.
    Returns None for an id that is neither known nor dialplan-prefixed."""
    existing = await get_call(call_id)
    if existing:
        return existing
    kind = next((k for p, k in DIALPLAN_PREFIX_KIND.items() if call_id.startswith(p)), None)
    if not kind:
        return None
    from routes.telephony_endpoints import endpoint_for_extension, resident_for_room
    ep = await endpoint_for_extension(from_extension)
    room = (ep or {}).get("room")
    resident = await resident_for_room(room)
    call = CallSession(call_id=call_id, kind=kind, from_extension=from_extension, room=room,
                       resident_id=(resident or {}).get("resident_id"), target_label=KIND_LABEL[kind],
                       conversation_session_id=f"phone_{call_id}" if kind == "aria" else None)
    doc = call.model_dump()
    doc["created_at"] = doc["created_at"].isoformat()
    doc["history"] = [{"state": "requested", "at": doc["created_at"], "source": "asterisk", "detail": None}]
    res = await db.call_sessions.update_one({"call_id": call_id}, {"$setOnInsert": doc}, upsert=True)
    if res.upserted_id is not None:
        await create_receipt(
            action_type=f"call.{kind}.requested", related_object_type="call", related_object_id=call_id,
            source="system", resident_id=doc.get("resident_id"), room=room,
            conversation_session_id=doc.get("conversation_session_id"),
        )
    return await get_call(call_id)


async def advance(call_id: str, new_state: str, *, source: str, detail: Optional[str] = None) -> dict:
    """Apply a state change reported by the phone system/provider. Returns
    {"applied": bool, "state": current}. Never raises for an out-of-order
    event - those are expected from a real PBX and simply ignored."""
    call = await db.call_sessions.find_one({"call_id": call_id}, {"_id": 0})
    if not call:
        return {"applied": False, "reason": "unknown_call"}
    current = call["state"]
    if new_state == current or new_state not in TRANSITIONS.get(current, set()):
        return {"applied": False, "state": current}
    at = _now()
    change = {"state": new_state, "at": at, "source": source, "detail": detail}
    update = {"$set": {"state": new_state}, "$push": {"history": change}}
    if new_state == "connected":
        update["$set"]["connected_at"] = at
    if new_state == "ended":
        update["$set"]["ended_at"] = at
        if detail:
            update["$set"]["hangup_cause"] = detail
    res = await db.call_sessions.update_one({"call_id": call_id, "state": current}, update)
    if res.modified_count == 0:  # a concurrent event won the race
        return {"applied": False, "state": (await get_call(call_id) or {}).get("state")}
    if new_state in TERMINAL_OUTCOMES:
        await create_receipt(
            action_type=f"call.{call['kind']}.{new_state}", related_object_type="call",
            related_object_id=call_id, source="system", resident_id=call.get("resident_id"),
            room=call.get("room"), conversation_session_id=call.get("conversation_session_id"),
            status="failed" if new_state == "failed" else "completed",
            result=f"{call.get('target_label') or call['kind']}: {new_state}" + (f" ({detail})" if detail else ""),
        )
    return {"applied": True, "state": new_state}


async def get_call(call_id: str) -> Optional[dict]:
    return await db.call_sessions.find_one({"call_id": call_id}, {"_id": 0})


def spoken_call_state(call: dict) -> str:
    """What Aria may truthfully say about a call - derived from state only."""
    who = call.get("target_label") or "them"
    return {
        "requested": f"I've asked the phone system to call {who}; it hasn't started dialing yet.",
        "dialing": f"The phone system is dialing {who} now.",
        "ringing": f"It's ringing at {who}. Nobody has answered yet.",
        "connected": f"{who} answered.",
        "unanswered": f"{who} didn't answer.",
        "failed": f"The call to {who} didn't go through.",
        "ended": f"The call with {who} has ended.",
    }[call["state"]]


@router.get("/calls")
async def list_calls(limit: int = 50, room: Optional[str] = None, user=Depends(require_admin)):
    q = {"room": room} if room else {}
    return await db.call_sessions.find(q, {"_id": 0}).sort("created_at", -1).to_list(min(limit, 200))


@router.get("/calls/{call_id}")
async def call_detail(call_id: str, user=Depends(require_admin)):
    call = await get_call(call_id)
    if not call:
        raise HTTPException(status_code=404, detail="Call not found")
    return call
