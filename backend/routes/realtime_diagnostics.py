"""Realtime voice diagnostics - append-only event log so a live-test defect
(phantom transcripts, double greetings, echo) can be reconstructed after the
fact from real event timing instead of guessed at. Called fire-and-forget
from useRealtimeVoice.js at each key Realtime event; never blocks the call
and never logs raw audio or secrets, only event type/timing/short text.
"""
from typing import Optional, Any
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from deps import db, get_current_user
from models import now_utc

router = APIRouter(prefix="/realtime-diagnostics", tags=["realtime-diagnostics"])


class DiagnosticEvent(BaseModel):
    session_id: str
    event_type: str                       # e.g. "speech_started", "user_transcript", "response_done"
    assistant_speaking: Optional[bool] = None   # was Aria's audio actively playing at this moment
    text: Optional[str] = None            # transcript text, when applicable - never raw audio
    response_id: Optional[str] = None
    meta: Optional[dict[str, Any]] = None


@router.post("/event")
async def log_event(data: DiagnosticEvent):
    """No auth - same trust model as the other kiosk-originated public
    endpoints. Fire-and-forget from the client; a failed log must never
    interrupt the call, so this always returns quickly."""
    await db.realtime_diagnostics.insert_one({
        "session_id": data.session_id,
        "event_type": data.event_type,
        "assistant_speaking": data.assistant_speaking,
        "text": data.text,
        "response_id": data.response_id,
        "meta": data.meta,
        "created_at": now_utc().isoformat(),
    })
    return {"ok": True}


@router.get("/session/{session_id}")
async def get_session_events(session_id: str, user=Depends(get_current_user)):
    """Contains transcript fragments, so authenticated staff/admin only -
    not the public trust tier the POST above uses. Chronological event
    timeline for one session, meant to be inspected right after a live
    acceptance test to prove what actually happened."""
    events = await db.realtime_diagnostics.find(
        {"session_id": session_id}, {"_id": 0},
    ).sort("created_at", 1).to_list(2000)
    return events
