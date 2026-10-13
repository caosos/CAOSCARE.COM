"""Shared check: does a request belong to a live Aria room session?

Used by /memory/realtime-turn (RQ-028) and /research (RQ-049). A session is
live while its room lease is active and fresh, or for a short grace after the
lease was released (the last turns/lookups often land just after release).
"""
from datetime import timedelta
from typing import Optional

from deps import db
from models import now_utc
from routes.realtime_room_lease import STALE_SECONDS

RELEASE_GRACE_SECONDS = 60


async def find_live_session(resident_id: str, session_id: str) -> Optional[dict]:
    """Return room and kiosk identity for a live (or just-released) session of that
    resident, else None."""
    if not resident_id or not session_id:
        return None
    now = now_utc()
    live = await db.resident_aria_leases.find_one({
        "session_id": session_id, "resident_id": resident_id,
        "status": {"$in": ["activating", "active"]},
        "last_seen_at": {"$gte": (now - timedelta(seconds=STALE_SECONDS)).isoformat()},
    })
    if live:
        return {"room": live.get("room"), "kiosk_id": live.get("kiosk_id")}
    released = await db.resident_aria_lease_events.find_one({
        "event": "released", "lease.session_id": session_id,
        "lease.resident_id": resident_id,
        "at": {"$gte": (now - timedelta(seconds=RELEASE_GRACE_SECONDS)).isoformat()},
    })
    lease = (released or {}).get("lease") or {}
    return {"room": lease.get("room"), "kiosk_id": lease.get("kiosk_id")} if released else None
