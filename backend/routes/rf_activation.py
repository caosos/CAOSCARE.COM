"""Room attention-incident activation gating for RF/auto_voice alerts.

Split out of rf.py (2026-08-30) - rf.py was already over the repo's
300-line cap, so the responsibility actually being changed (this) moves
out rather than growing that file further.

Owns the "does this device already have an open, unconsumed attention
incident, or does this press need a fresh one" decision. An incident opens
when its alert is created and stays open until Alert.activation_consumed_at
is set - which happens when the triggering session's room lease is
released (see realtime_room_lease.py's release()), not on a fixed timer.

2026-08-30 (real live defect, room 401): the prior fix collapsed RF frames
within a fixed 8s window into one alert's press_count, but a repeat press
~30s+ into an ALREADY ACTIVE Resident Aria session fell outside that
window and minted a second, independent alert. It sat unconsumed until the
first session ended, at which point the kiosk's active-emergency poll
picked it up as "new" and auto-launched a second session with no new
physical press. This module is the fix: coalescing is keyed on incident
state, not elapsed time.
"""
from datetime import datetime, timedelta
from typing import Optional

from deps import db
from models import now_utc

# Last-resort safety net only - for an incident that never got a session at
# all (mic denied, kiosk never tapped), so a truly abandoned alert can't
# block the room forever. Deliberately far longer than any plausible real
# session (OpenAI's own Realtime hard cap is 60 minutes, per TSB-002).
OPEN_INCIDENT_MAX_AGE_SECONDS = 90 * 60


async def try_coalesce_press(rf_device_id: str, score: float, raw_event: dict) -> Optional[dict]:
    """If this device already has an open incident, attach this press to it
    (persist raw_event, bump press_count) and return the /rf/event response
    dict to return early with. Returns None if there's no open incident (or
    it's aged past the safety net) - caller should create a fresh alert."""
    open_alert = await db.alerts.find_one(
        {"source_metadata.rf_device_id": rf_device_id, "activation_consumed_at": None},
        {"_id": 0, "alert_id": 1, "created_at": 1},
        sort=[("created_at", -1)],
    )
    if not open_alert:
        return None
    created_at = open_alert["created_at"]
    if isinstance(created_at, str):
        created_at = datetime.fromisoformat(created_at)
    if (now_utc() - created_at) >= timedelta(seconds=OPEN_INCIDENT_MAX_AGE_SECONDS):
        return None

    await db.alerts.update_one({"alert_id": open_alert["alert_id"]}, {"$inc": {"press_count": 1}})
    raw_event["alert_id"] = open_alert["alert_id"]
    await db.rf_events.insert_one(raw_event)
    raw_event.pop("_id", None)
    return {
        "ok": True, "matched": True, "score": round(score, 4),
        "device_id": rf_device_id, "alert_id": open_alert["alert_id"],
        "press_coalesced": True,
    }
