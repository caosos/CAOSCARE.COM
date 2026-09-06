"""Level 1 resident-assistance event lifecycle actions (2026-09-06
directive) - split out of routes/alerts.py (already at the 300-line cap)
so the base alert CRUD/ack/resolve/close endpoints don't get buried under
the newer Aria/live-line transitions. Same `/alerts` URL prefix, a
separate router registered alongside the original in server.py.

Public: aria-event, live-line/ring, and live-line/no-answer all fire from
the resident-facing Realtime voice session (frontend/src/lib/
useRealtimeVoice.js), which has no staff login - same trust model as
POST /alerts and POST /rf/event. live-line/answer is staff-only.
"""
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from models import now_utc
from deps import db, get_current_user
from routes.resident_activation import try_call_on_call_phone

router = APIRouter(prefix="/alerts", tags=["alerts"])

_ARIA_STATE_FOR_EVENT = {
    "activated": "active", "dismissed": "dismissed", "timeout": "dismissed",
}


class AriaEventInput(BaseModel):
    event: str  # "activated" | "dismissed" | "timeout" | "silence_after_invite" | "requested_staff"
    utterance: Optional[str] = None


@router.post("/{alert_id}/aria-event")
async def aria_event(alert_id: str, data: AriaEventInput):
    """Single code path for every Aria lifecycle transition on an open
    event, instead of one endpoint per transition.

    2026-09-06 (decouple ResidentEvent lifetime from Realtime session
    lifetime): this is now the ONLY place a session end can mark
    activation_consumed_at (besides staff_present()) - and only for
    "dismissed"/"timeout", the two reasons that actually mean "this
    resident-caused conversational cycle concluded, don't immediately
    relaunch." routes/realtime_room_lease.py::release() no longer touches
    it at all, because release() fires identically whether the resident
    said goodbye or the connection just died - it has no way to tell
    those apart, so it must not guess. Every other way a session can end
    (network drop, ICE failure, a moved/failed-over endpoint, an
    in-flight auto-reconnect, a plain component unmount) leaves
    activation_consumed_at untouched, so the SAME event stays
    immediately relaunchable without a fresh physical press."""
    existing = await db.alerts.find_one({"alert_id": alert_id}, {"_id": 0})
    if not existing:
        raise HTTPException(status_code=404, detail="Alert not found")

    update: dict = {}
    if data.event in _ARIA_STATE_FOR_EVENT:
        update["aria_state"] = _ARIA_STATE_FOR_EVENT[data.event]
        if data.event in ("dismissed", "timeout"):
            update["activation_consumed_at"] = now_utc().isoformat()
    elif data.event == "silence_after_invite":
        update["silence_after_invite"] = True
    elif data.event == "requested_staff":
        update["requested_staff"] = True
        if data.utterance:
            update["resident_stated_reason"] = data.utterance
    else:
        raise HTTPException(status_code=400, detail=f"Unknown aria-event: {data.event}")

    log_entry = {"at": now_utc().isoformat(), "field": data.event, "utterance": data.utterance}
    await db.alerts.update_one(
        {"alert_id": alert_id}, {"$set": update, "$push": {"event_log": log_entry}},
    )
    doc = await db.alerts.find_one({"alert_id": alert_id}, {"_id": 0})
    return doc


@router.post("/{alert_id}/live-line/ring")
async def live_line_ring(alert_id: str):
    """Resident asked for staff now (or stayed silent after the routing
    question, which defaults to "now" per the directive). Both halves of
    the "Both" live-line decision fire here: an urgent state staff's
    already-open dashboard picks up via alerts_feed, and a best-effort
    Twilio call - a real no-op today since this deployment has no Twilio
    credentials, same as routes/escalation.py's existing SMS path."""
    existing = await db.alerts.find_one({"alert_id": alert_id}, {"_id": 0})
    if not existing:
        raise HTTPException(status_code=404, detail="Alert not found")
    await db.alerts.update_one(
        {"alert_id": alert_id},
        {
            "$set": {"live_line_state": "ringing", "requested_staff": True},
            "$push": {"event_log": {"at": now_utc().isoformat(), "field": "live_line", "to": "ringing"}},
        },
    )
    try:
        await try_call_on_call_phone(existing.get("room"), existing.get("resident_name"))
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"live-line call attempt failed for {alert_id}: {e}")
    doc = await db.alerts.find_one({"alert_id": alert_id}, {"_id": 0})
    return doc


async def _set_live_line_state(alert_id: str, state: str) -> dict:
    r = await db.alerts.update_one(
        {"alert_id": alert_id, "live_line_state": "ringing"},
        {
            "$set": {"live_line_state": state},
            "$push": {"event_log": {"at": now_utc().isoformat(), "field": "live_line", "to": state}},
        },
    )
    if r.matched_count == 0:
        raise HTTPException(status_code=404, detail="Alert not found or not currently ringing")
    return await db.alerts.find_one({"alert_id": alert_id}, {"_id": 0})


class LiveLineAnswerInput(BaseModel):
    state: str = "connected"  # "connected" | "declined"


@router.post("/{alert_id}/live-line/answer")
async def live_line_answer(alert_id: str, data: LiveLineAnswerInput, user=Depends(get_current_user)):
    """Staff-only: answers or declines from the dashboard banner."""
    if data.state not in ("connected", "declined"):
        raise HTTPException(status_code=400, detail="state must be connected or declined")
    return await _set_live_line_state(alert_id, data.state)


@router.post("/{alert_id}/live-line/no-answer")
async def live_line_no_answer(alert_id: str):
    """Public: the resident's own kiosk session self-reports the ring
    timeout expiring with nobody having answered (no staff login exists on
    that side) - see useRealtimeVoice.js's ring-timeout timer."""
    return await _set_live_line_state(alert_id, "no_answer")
