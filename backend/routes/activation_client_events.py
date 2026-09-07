"""Public endpoint for kiosk/client activation breadcrumbs.

The kiosk is the one participant with no server-side record of when it was
present. This lets it POST a small, allow-listed batch of state-transition
breadcrumbs into db.activation_events (via routes/activation_log.alog) so
"when was the kiosk actually mounted / polling / did it accept this alert
and why" becomes answerable.

Same trust tier as POST /rf/event and POST /realtime-diagnostics/event:
no auth, fire-and-forget, never blocks the kiosk. Unknown event names and
oversized batches are dropped, not errored. Never carries raw audio.
"""
from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel

from routes.activation_log import alog

router = APIRouter(prefix="/activation-events", tags=["activation-observability"])

# Only transitions and meaningful poll results - never idle polls.
_KIOSK_EVENTS = {
    "kiosk_mounted", "kiosk_unmounted", "page_hidden", "page_visible",
    "poll_started", "poll_stopped", "alert_first_seen", "alert_cleared",
    "wake_accepted", "wake_rejected",
}
_REALTIME_EVENTS = {
    "mic_requested", "mic_acquired", "mic_failed",
    "session_mint_started", "session_ended_client",
}
_ALLOWED = _KIOSK_EVENTS | _REALTIME_EVENTS


class ClientEvent(BaseModel):
    event: str
    client_instance_id: str
    room: Optional[str] = None
    kiosk_id: Optional[str] = None
    resident_id: Optional[str] = None
    alert_id: Optional[str] = None
    activation_id: Optional[str] = None
    session_id: Optional[str] = None
    ts_client: Optional[str] = None
    data: Optional[dict] = None


class ClientEventBatch(BaseModel):
    events: list[ClientEvent]


@router.post("/client")
async def client_events(batch: ClientEventBatch):
    accepted = 0
    for e in batch.events[:50]:
        if e.event not in _ALLOWED:
            continue
        await alog(
            "realtime" if e.event in _REALTIME_EVENTS else "kiosk",
            e.event,
            activation_id=e.activation_id, room=e.room, resident_id=e.resident_id,
            alert_id=e.alert_id, kiosk_id=e.kiosk_id, client_instance_id=e.client_instance_id,
            session_id=e.session_id, data=e.data, ts_client=e.ts_client,
        )
        accepted += 1
    return {"ok": True, "accepted": accepted, "dropped": max(0, len(batch.events) - accepted)}
