"""Realtime voice turn persistence - split out of memory.py to keep it
under the 300-line cap. Owns exactly one endpoint: saving each Realtime
voice turn the instant it's known, independently, with no pairing at the
persistence layer (see RealtimeTurnIngest's docstring for the real bug
this replaced). Reuses memory.py's extract_and_store_memories() rather
than duplicating extraction logic - this file only decides when to call it
and what to pass.
"""
import asyncio
from typing import Optional, Literal
from fastapi import APIRouter
from pydantic import BaseModel

from deps import db
from models import now_utc
from routes.memory import extract_and_store_memories

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
    resident_id: str
    session_id: str
    role: Literal["user", "assistant"]
    text: str
    room: Optional[str] = None            # kiosk room at call time - for Resident Record -> Conversations
    kiosk_id: Optional[str] = None
    item_id: Optional[str] = None         # OpenAI conversation item id, when the client has it - traceability
    # False when the client flagged a USER turn as having started while
    # Aria's own audio was still playing (likely echo/VAD false-positive,
    # not real resident speech) - see realtimeMessageHandler.js's
    # speech_started handler. Meaningless for role="assistant".
    # A questionable transcript must not silently become durable memory,
    # so it's still kept in the conversation log (diagnostic value) but
    # skipped from fact extraction below.
    trusted: bool = True


@router.post("/realtime-turn")
async def realtime_turn_ingest(data: RealtimeTurnIngest):
    """Public — called from the kiosk during a voice call, once per turn.
    Persists into db.conversations immediately (so future sessions can
    replay context, and nothing depends on later events arriving) and,
    only on the assistant side, fires the background memory extractor -
    paired against the most recent USER turn already durably saved for
    this session, not a fragile client-side ref. An untrusted user turn
    is still saved (diagnostic/history value) but is skipped for pairing,
    so it can never become durable memory."""
    text = (data.text or "").strip()
    if not data.resident_id or not text:
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
