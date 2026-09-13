"""Fence voice work to the current event activation and audio owner.

A cycle spans repeat presses during one conversation. A post-dismissal
press starts a new cycle; delayed work from the old cycle cannot consume
or start the new one. No resident-event status is closed by this module.
"""
from fastapi import HTTPException
from deps import db
from models import now_utc


async def validate_activation(payload):
    alert_id = payload.get("alert_id")
    if not alert_id:
        return None  # Existing manual, non-event voice path.
    activation_id = payload.get("activation_id")
    if not activation_id:
        raise HTTPException(409, "Fresh resident activation required")
    event = await db.alerts.find_one({
        "alert_id": alert_id, "activation_id": activation_id,
        "status": {"$in": ["active", "acknowledged"]},
        "activation_consumed_at": None,
    }, {"_id": 0})
    if not event:
        raise HTTPException(409, "Resident activation is no longer current")
    if not payload.get("room") or event.get("room") != payload["room"]:
        raise HTTPException(409, "Resident activation belongs to another room")
    if event.get("resident_id") != payload.get("resident_id"):
        raise HTTPException(409, "Resident activation belongs to another resident")
    kiosk_id = payload.get("kiosk_id")
    if kiosk_id:
        kiosk = await db.kiosks.find_one({"kiosk_id": kiosk_id}, {"room": 1})
        if not kiosk or kiosk.get("room") != event.get("room"):
            raise HTTPException(409, "Kiosk does not own this room")
    return event


async def bind_activation(payload, session_id):
    event = await validate_activation(payload)
    if not event:
        return
    result = await db.alerts.update_one({
        "alert_id": event["alert_id"], "activation_id": event["activation_id"],
        "status": {"$in": ["active", "acknowledged"]}, "activation_consumed_at": None,
    }, {"$set": {"aria_session_id": session_id}, "$push": {"event_log": {
        "at": now_utc().isoformat(), "field": "session_bound",
        "session_id": session_id, "activation_id": event["activation_id"],
    }}})
    if not result.matched_count:
        raise HTTPException(409, "Resident activation changed during session setup")
