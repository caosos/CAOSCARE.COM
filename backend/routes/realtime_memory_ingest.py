"""Realtime voice turn persistence - split out of memory.py to keep it
under the 300-line cap. Owns exactly one endpoint: saving each Realtime
voice turn the instant it's known, independently, with no pairing at the
persistence layer (see RealtimeTurnIngest's docstring for the real bug
this replaced). Reuses memory.py's extract_and_store_memories() rather
than duplicating extraction logic - this file only decides when to call it
and what to pass.
"""
import asyncio
from datetime import timedelta
from typing import Optional, Literal
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from deps import db
from models import now_utc
from routes.memory import extract_and_store_memories
from routes.realtime_room_lease import STALE_SECONDS

# RQ-028: how long after a session's lease is released its last turns are
# still accepted (the final assistant turn often lands just after release).
RELEASE_GRACE_SECONDS = 60
MAX_TURN_CHARS = 4000

router = APIRouter(prefix="/memory", tags=["memory-realtime-ingest"])


class RealtimeTurnIngest(BaseModel):
    """ONE turn (user or assistant) from a WebRTC voice session, saved the
    instant it's known - captured client-side in realtimeMessageHandler.js.

    2026-08-22 (real bug, confirmed live): this used to accept a paired
    {user_text, assistant_text} and save both together when the assistant
    side arrived. A single `pendingUserRef` held only the most recent
    unpaired user transcript client-side, so a resident's real ~15-second
    correction got silently overwritten - and lost, never saved anywhere -
    when they continued speaking again before Aria's reply completed.
    Fixed by removing pairing from persistence entirely: every turn is
    saved independently, in arrival order, the moment it's known. Nothing
    depends on a second turn NOT arriving first."""
    resident_id: str = Field(min_length=1, max_length=100)
    session_id: str = Field(min_length=1, max_length=100)
    role: Literal["user", "assistant"]
    text: str = Field(max_length=MAX_TURN_CHARS)
    room: Optional[str] = Field(default=None, max_length=100)  # kiosk room at call time - for Resident Record -> Conversations
    kiosk_id: Optional[str] = Field(default=None, max_length=100)
    item_id: Optional[str] = Field(default=None, max_length=200)         # OpenAI conversation item id, when the client has it - traceability
    # False when the client flagged a USER turn as having started while
    # Aria's own audio was still playing (likely echo/VAD false-positive,
    # not real resident speech) - see realtimeMessageHandler.js's
    # speech_started handler. Meaningless for role="assistant".
    # A questionable transcript must not silently become durable memory,
    # so it's still kept in the conversation log (diagnostic value) but
    # skipped from fact extraction below.
    # RQ-028: this flag is an echo-quality signal ONLY, never a security
    # control. The server cannot verify it; it is only reachable by a caller
    # that already holds a live lease for this resident+session (below), so it
    # can only affect what that live session may already write. It never
    # widens who may write.
    trusted: bool = True


async def _session_grounding_error(data: "RealtimeTurnIngest") -> Optional[str]:
    """None if the turn belongs to a live Aria session for this resident
    (or one released within RELEASE_GRACE_SECONDS); otherwise why not."""
    now = now_utc()
    live = await db.resident_aria_leases.find_one({
        "session_id": data.session_id, "resident_id": data.resident_id,
        "status": {"$in": ["activating", "active"]},
        "last_seen_at": {"$gte": (now - timedelta(seconds=STALE_SECONDS)).isoformat()},
    })
    if live:
        return None
    released = await db.resident_aria_lease_events.find_one({
        "event": "released", "lease.session_id": data.session_id,
        "lease.resident_id": data.resident_id,
        "at": {"$gte": (now - timedelta(seconds=RELEASE_GRACE_SECONDS)).isoformat()},
    })
    return None if released else "no live session for this resident"


@router.post("/realtime-turn")
async def realtime_turn_ingest(data: RealtimeTurnIngest):
    """Called from the kiosk (no login) but only accepted for a live Aria session
    of that resident (RQ-028) - see _session_grounding_error. Called from the kiosk during a voice call, once per turn.
    Persists into db.conversations immediately (so future sessions can
    replay context, and nothing depends on later events arriving) and,
    only on the assistant side, fires the background memory extractor -
    paired against the most recent USER turn already durably saved for
    this session, not a fragile client-side ref. An untrusted user turn
    is still saved (diagnostic/history value) but is skipped for pairing,
    so it can never become durable memory."""
    text = (data.text or "").strip()
    if not text:
        return {"ok": False, "saved": 0, "skipped": "empty"}
    why = await _session_grounding_error(data)
    if why:
        raise HTTPException(status_code=403, detail=f"Turn not stored: {why}")
    return await store_turn(data)


async def store_turn(data: RealtimeTurnIngest):
    """Persist one already-authorized turn. In-process callers that hold their
    own server-side authority (the telephone sideband, which has a call
    record, not a room lease) call this directly; the HTTP route above is
    the only path that needs the session check."""
    text = (data.text or "").strip()
    if not text:
        return {"ok": False, "saved": 0, "skipped": "empty"}
    now = now_utc().isoformat()
    await db.conversations.insert_one({
        "resident_id": data.resident_id,
        "session_id": data.session_id or "realtime",
        "role": data.role,
        "content": text,
        "source": "realtime",
        "trusted": data.trusted if data.role == "user" else None,
        "room": data.room,
        "kiosk_id": data.kiosk_id,
        "item_id": data.item_id,
        "created_at": now,
    })
    if data.role != "assistant":
        return {"ok": True}
    prior_user = await db.conversations.find_one(
        {"resident_id": data.resident_id, "session_id": data.session_id or "realtime", "role": "user"},
        {"_id": 0}, sort=[("created_at", -1)],
    )
    if not prior_user or prior_user.get("trusted") is False:
        return {"ok": True, "extraction_skipped": "no_trusted_user_turn"}
    # Fire-and-forget extraction. Never block the kiosk.
    asyncio.create_task(extract_and_store_memories(
        data.resident_id, data.session_id or "realtime",
        prior_user["content"], text,
    ))
    return {"ok": True}
