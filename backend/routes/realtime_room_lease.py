"""Resident Aria room-session lease.

Server-side singleton so at most one active Resident Aria voice session can
own a given room's audio at a time. Fixes a real, live-evidenced defect
(2026-08-29): repeated RF pendant frames and/or multiple kiosk tabs each
independently minted a fresh OpenAI Realtime session with zero server-side
concept of "one is already active" - two sessions spoke over the same
physical mic simultaneously. See docs/tsb for the incident record.

`claim_or_reuse_room_lease()` is called in-process (no HTTP round trip) from
POST /realtime/session before it spends a real OpenAI API call - a losing
caller never opens a mic or a peer connection at all. The same function
backs POST /realtime/room/{room}/activate for any other trigger source
(pendant, future wake-word, handset) that wants to check/claim ahead of
starting a conversation through a different path.

Staleness: a connected client heartbeats its lease. If last_seen_at is
older than STALE_SECONDS, the room is treated as available again, so a
crashed tab or lost network can never permanently lock a room.
"""
import uuid
from datetime import timedelta
from typing import Optional

from fastapi import APIRouter, Body
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from deps import db
from models import now_utc

router = APIRouter(prefix="/realtime/room", tags=["realtime"])

STALE_SECONDS = 45


async def claim_or_reuse_room_lease(
    room: str,
    resident_id: Optional[str],
    kiosk_id: Optional[str],
    trigger_source: str,
    session_id: Optional[str] = None,
) -> dict:
    """Atomically claim `room`'s lease, or report the existing live one.

    `session_id`, when supplied, is reused as-is (the caller already has a
    stable id it wants to keep, e.g. the frontend's own rt_<rand>_<ts>).
    Otherwise one is minted here."""
    await db.resident_aria_leases.create_index("room", unique=True)
    now = now_utc()
    stale_cutoff = (now - timedelta(seconds=STALE_SECONDS)).isoformat()
    sid = session_id or f"rlease_{uuid.uuid4().hex[:12]}"
    new_doc = {
        "room": room, "resident_id": resident_id, "kiosk_id": kiosk_id,
        "session_id": sid, "status": "activating", "trigger_source": trigger_source,
        "created_at": now.isoformat(), "last_seen_at": now.isoformat(),
    }

    # Try to atomically steal a claimable lease (missing status, or stale).
    result = await db.resident_aria_leases.find_one_and_update(
        {"room": room, "$or": [
            {"status": {"$nin": ["activating", "active"]}},
            {"last_seen_at": {"$lt": stale_cutoff}},
        ]},
        {"$set": new_doc},
        return_document=ReturnDocument.AFTER,
    )
    if result and result.get("session_id") == sid:
        return {"claimed": True, "session_id": sid, "status": "activating"}

    # No existing doc matched the "claimable" filter at all - try a fresh
    # insert (covers "no lease exists yet for this room"). If another
    # request wins the race between our check and this insert, Mongo's
    # unique index on `room` rejects ours - that's the correct outcome.
    try:
        await db.resident_aria_leases.insert_one(dict(new_doc))
        return {"claimed": True, "session_id": sid, "status": "activating"}
    except DuplicateKeyError:
        existing = await db.resident_aria_leases.find_one({"room": room}, {"_id": 0})
        return {"claimed": False, "session_id": existing["session_id"], "status": existing.get("status"), "reason": "already_active"}


@router.post("/{room}/activate")
async def activate(room: str, payload: dict = Body(default={})):
    """HTTP entry point for non-/session triggers (pendant, future wake
    word/handset) that want to claim the room before starting a
    conversation through their own path."""
    return await claim_or_reuse_room_lease(
        room, payload.get("resident_id"), payload.get("kiosk_id"),
        payload.get("trigger_source") or "unknown", payload.get("session_id"),
    )


@router.post("/{room}/heartbeat")
async def heartbeat(room: str, payload: dict = Body(default={})):
    """Connected client keeps its lease alive. No-ops (ok:false) if this
    session_id doesn't hold the current lease - e.g. it was already
    reclaimed as stale, so the caller should stop and re-negotiate."""
    session_id = payload.get("session_id")
    r = await db.resident_aria_leases.update_one(
        {"room": room, "session_id": session_id, "status": {"$in": ["activating", "active"]}},
        {"$set": {"status": "active", "last_seen_at": now_utc().isoformat()}},
    )
    return {"ok": r.matched_count > 0}


@router.post("/{room}/release")
async def release(room: str, payload: dict = Body(default={})):
    """End of conversation - free the room immediately rather than waiting
    out the stale-lease grace period. Only releases if this session_id
    actually holds the lease, so a stale/duplicate caller can't release
    someone else's active session.

    2026-08-30 (real live defect): also closes out the room's attention
    incident(s) - see Alert.activation_consumed_at in models.py and the
    coalescing logic in routes/rf.py. Without this, a repeat pendant press
    during the call that had minted its own alert (or any future auto_voice
    alert for this room) stayed "open" after the call ended and the
    kiosk's active-emergency poll would auto-launch a second session from
    it with no new physical press - evidenced live, room 401."""
    session_id = payload.get("session_id")
    r = await db.resident_aria_leases.delete_one({"room": room, "session_id": session_id})
    if r.deleted_count > 0:
        await db.alerts.update_many(
            {"room": room, "auto_voice": True, "activation_consumed_at": None},
            {"$set": {"activation_consumed_at": now_utc().isoformat()}},
        )
    return {"ok": r.deleted_count > 0}


@router.get("/{room}/status")
async def lease_status(room: str):
    """Read-only - lets Admin/staff surfaces show whether a room is
    currently occupied by a live Resident Aria session."""
    doc = await db.resident_aria_leases.find_one({"room": room}, {"_id": 0})
    return {"lease": doc}


@router.post("/{room}/staff-present")
async def staff_present(room: str):
    """Level 1 directive (2026-09-06): staff physically in the room
    immediately mutes Aria and drops any live line - no hardware exists
    yet to call this automatically (no RFID/badge/tablet-presence in this
    deployment), so this is a real, callable hook with no UI trigger wired
    to it yet, built ahead of that hardware decision rather than waiting
    on it. Mirrors release()'s own alert-consumption + lease-drop shape."""
    lease = await db.resident_aria_leases.find_one({"room": room}, {"_id": 0})
    if lease:
        await db.resident_aria_leases.delete_one({"room": room, "session_id": lease["session_id"]})
    r = await db.alerts.update_many(
        {"room": room, "status": {"$in": ["active", "acknowledged"]}},
        {
            "$set": {
                "aria_state": "muted_staff",
                "live_line_state": "none",
                "activation_consumed_at": now_utc().isoformat(),
            },
            "$push": {"event_log": {"at": now_utc().isoformat(), "field": "aria_state", "to": "muted_staff"}},
        },
    )
    return {"ok": True, "lease_dropped": bool(lease), "events_muted": r.modified_count}
