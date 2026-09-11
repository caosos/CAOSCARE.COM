"""Conversation-parity turn-taking instrumentation (Terminal 10).

Derives measurable turn-taking signals from the realtime_diagnostics event
log useRealtimeVoice.js ALREADY writes on every session (speech_started/
speech_stopped, response_created/response_done) - no new frontend capture
needed. `assistant_speaking` is already populated per event; verified
against real session history before writing this (250 of 857 real
speech_started rows across sessions carry assistant_speaking=True - i.e.
real, already-recorded barge-ins), so barge-in/interruption detection is a
pure derivation, not new instrumentation.

Read-only. No new events are written here; no raw audio or transcript text
is read or returned - only counts/timestamps/durations, so this stays
public like the other Aria context inspection endpoints (unlike
GET /realtime-diagnostics/session/{id}, which carries transcript fragments
and is staff-authenticated).
"""
from typing import Optional

from fastapi import APIRouter

from deps import db
from routes.aria_time import parse_dt

router = APIRouter(prefix="/aria/turn-taking", tags=["realtime"])

# Aria took noticeably long to start responding after the resident stopped
# talking - a candidate "the pause felt awkward" signal.
LONG_GAP_MS = 4000
# A barge-in this soon after Aria started a response suggests she spoke
# before the resident was actually done, not a genuine interruption of a
# fully-formed reply.
PREMATURE_INTERRUPT_MS = 600

_EVENTS = ("speech_started", "speech_stopped", "response_created", "response_done")


def _ms(earlier_iso, later_iso) -> Optional[float]:
    try:
        return (parse_dt(later_iso) - parse_dt(earlier_iso)).total_seconds() * 1000
    except Exception:
        return None


def _avg(xs: list) -> Optional[float]:
    return round(sum(xs) / len(xs), 1) if xs else None


async def resolve_turn_taking(session_id: str) -> dict:
    """One pass over the session's own event stream, in order. Every
    metric is derived - nothing here writes a new diagnostic event."""
    rows = await db.realtime_diagnostics.find(
        {"session_id": session_id, "event_type": {"$in": _EVENTS}},
        {"_id": 0, "event_type": 1, "assistant_speaking": 1, "created_at": 1},
    ).sort("created_at", 1).to_list(4000)

    barge_in_at: list = []
    premature_interrupt_at: list = []
    response_gaps_ms: list = []
    response_durations_ms: list = []
    user_turns = assistant_turns = 0
    last_speech_stopped_at = last_response_created_at = None

    for r in rows:
        et, at = r["event_type"], r.get("created_at")
        if et == "speech_started":
            user_turns += 1
            if r.get("assistant_speaking") is True:
                barge_in_at.append(at)
                gap = _ms(last_response_created_at, at) if last_response_created_at else None
                if gap is not None and 0 <= gap <= PREMATURE_INTERRUPT_MS:
                    premature_interrupt_at.append(at)
        elif et == "speech_stopped":
            last_speech_stopped_at = at
        elif et == "response_created":
            assistant_turns += 1
            last_response_created_at = at
            if last_speech_stopped_at is not None:
                gap = _ms(last_speech_stopped_at, at)
                if gap is not None and gap >= 0:
                    response_gaps_ms.append(gap)
                last_speech_stopped_at = None  # each gap consumed once
        elif et == "response_done" and last_response_created_at is not None:
            dur = _ms(last_response_created_at, at)
            if dur is not None:
                response_durations_ms.append(dur)

    long_gaps = [g for g in response_gaps_ms if g >= LONG_GAP_MS]
    return {
        "session_id": session_id,
        "user_turn_count": user_turns,
        "assistant_turn_count": assistant_turns,
        "barge_in_count": len(barge_in_at),
        "barge_in_at": barge_in_at,
        "premature_interrupt_count": len(premature_interrupt_at),
        "avg_silence_before_response_ms": _avg(response_gaps_ms),
        "max_silence_before_response_ms": max(response_gaps_ms) if response_gaps_ms else None,
        "long_gap_count": len(long_gaps),
        "long_gap_threshold_ms": LONG_GAP_MS,
        "avg_response_duration_ms": _avg(response_durations_ms),
        "premature_interrupt_threshold_ms": PREMATURE_INTERRUPT_MS,
    }


@router.get("/{session_id}")
async def turn_taking(session_id: str):
    return await resolve_turn_taking(session_id)
