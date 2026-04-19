"""Pendant registry + RF ingest from Android bridge app (USB receiver)."""
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Depends, Request
from models import Pendant, PendantCreate, PendantEventInput, Alert, now_utc
from deps import db, get_current_user

router = APIRouter(prefix="/pendants", tags=["pendants"])


def _iso(doc: dict) -> dict:
    for k in ("created_at", "last_seen_at"):
        v = doc.get(k)
        if v and not isinstance(v, str):
            doc[k] = v.isoformat()
    return doc


@router.get("")
async def list_pendants(user=Depends(get_current_user)):
    items = await db.pendants.find({}, {"_id": 0}).sort("frequency_mhz", 1).to_list(1000)
    # attach resident name for convenience
    out = []
    for p in items:
        _iso(p)
        if p.get("resident_id"):
            r = await db.residents.find_one({"resident_id": p["resident_id"]}, {"_id": 0, "name": 1, "room": 1})
            if r:
                p["resident_name"] = r.get("name")
                p["room"] = r.get("room")
        out.append(p)
    return out


@router.post("")
async def create_pendant(data: PendantCreate, user=Depends(get_current_user)):
    existing = await db.pendants.find_one({"frequency_mhz": data.frequency_mhz}, {"_id": 0})
    if existing:
        raise HTTPException(status_code=400, detail="Frequency already registered")
    p = Pendant(**data.model_dump())
    doc = p.model_dump()
    doc["created_at"] = doc["created_at"].isoformat()
    doc["last_seen_at"] = None
    await db.pendants.insert_one(doc)
    doc.pop("_id", None)
    return doc


@router.put("/{pendant_device_id}")
async def update_pendant(pendant_device_id: str, data: PendantCreate, user=Depends(get_current_user)):
    r = await db.pendants.update_one(
        {"pendant_device_id": pendant_device_id},
        {"$set": data.model_dump()},
    )
    if r.matched_count == 0:
        raise HTTPException(status_code=404, detail="Pendant not found")
    doc = await db.pendants.find_one({"pendant_device_id": pendant_device_id}, {"_id": 0})
    return _iso(doc)


@router.delete("/{pendant_device_id}")
async def delete_pendant(pendant_device_id: str, user=Depends(get_current_user)):
    r = await db.pendants.delete_one({"pendant_device_id": pendant_device_id})
    if r.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Pendant not found")
    return {"ok": True}


@router.post("/event")
async def pendant_event(evt: PendantEventInput, request: Request):
    """
    Public ingest endpoint.
    The Android bridge app connected to a USB RF receiver POSTs here when a pendant transmits.
    We look up the pendant by frequency, update its last_seen/battery/signal, and — for press/fall
    events — automatically create an alert linked to the pendant's assigned resident.
    """
    from routes.device_auth import verify_device_token
    await verify_device_token(request, "pendants.event")

    pendant = await db.pendants.find_one({"frequency_mhz": evt.frequency_mhz}, {"_id": 0})
    if not pendant:
        # Persist as an unregistered ping so admins can see it and map it
        await db.pendant_unknown.insert_one({
            "frequency_mhz": evt.frequency_mhz,
            "signal_strength": evt.signal_strength,
            "event_type": evt.event_type,
            "zone": evt.zone,
            "seen_at": now_utc().isoformat(),
        })
        raise HTTPException(
            status_code=404,
            detail=f"No pendant registered at {evt.frequency_mhz} MHz. Logged as unregistered.",
        )

    # Update pendant telemetry
    update = {"last_seen_at": now_utc().isoformat()}
    if evt.signal_strength is not None:
        update["signal_strength"] = evt.signal_strength
    if evt.battery_percent is not None:
        update["battery_percent"] = evt.battery_percent
        if evt.battery_percent < 15 and pendant.get("status") == "active":
            update["status"] = "low_battery"
    await db.pendants.update_one(
        {"pendant_device_id": pendant["pendant_device_id"]},
        {"$set": update},
    )

    # Record location ping if zone provided
    if evt.zone and pendant.get("resident_id"):
        loc_doc = {
            "update_id": f"loc_{datetime.now(timezone.utc).timestamp()}",
            "resident_id": pendant["resident_id"],
            "zone": evt.zone,
            "signal_strength": evt.signal_strength,
            "source": "pendant",
            "created_at": now_utc().isoformat(),
        }
        await db.locations.insert_one(loc_doc)
        loc_doc.pop("_id", None)

    # No alert for periodic pings
    if evt.event_type == "periodic_ping":
        return {"ok": True, "pendant": pendant["pendant_device_id"], "alert": None}

    # Create alert
    resident_name = None
    room = None
    if pendant.get("resident_id"):
        r = await db.residents.find_one({"resident_id": pendant["resident_id"]}, {"_id": 0})
        if r:
            resident_name = r["name"]
            room = r.get("room")

    # --- Auto-voice & panic-press detection --------------------------------
    # EVERY pendant press must auto-start the kiosk's voice conversation so a
    # resident who can't reach the screen — or who is blind — is heard.
    # Panic-press (>=2 presses in 60s) or a fall event additionally escalates
    # the severity to "emergency".
    from datetime import timedelta
    press_count = 1
    auto_voice = True   # default ON — we always want voice for pendant events
    severity = "emergency" if evt.event_type == "fall" else "assist"

    if evt.event_type == "press" and pendant.get("pendant_id"):
        window_start = (now_utc() - timedelta(seconds=60)).isoformat()
        recent = await db.alerts.count_documents({
            "pendant_id": pendant["pendant_id"],
            "triggered_by": "pendant",
            "created_at": {"$gte": window_start},
        })
        press_count = recent + 1
        if press_count >= 2:
            severity = "emergency"

    alert = Alert(
        pendant_id=pendant["pendant_id"],
        frequency=evt.frequency_mhz,
        resident_id=pendant.get("resident_id"),
        resident_name=resident_name,
        room=room,
        zone=evt.zone,
        severity=severity,
        message=(
            f"Panic-press ×{press_count} at {evt.frequency_mhz} MHz"
            if press_count >= 2 and evt.event_type == "press"
            else f"Pendant {evt.event_type.replace('_', ' ')} at {evt.frequency_mhz} MHz"
        ),
        triggered_by="pendant",
        auto_voice=auto_voice,
        press_count=press_count,
    )
    doc = alert.model_dump()
    doc["created_at"] = doc["created_at"].isoformat()
    doc["acknowledged_at"] = None
    doc["resolved_at"] = None
    await db.alerts.insert_one(doc)
    doc.pop("_id", None)
    return {"ok": True, "pendant": pendant["pendant_device_id"], "alert": doc}


@router.get("/unknown")
async def list_unknown_pings(user=Depends(get_current_user)):
    items = await db.pendant_unknown.find({}, {"_id": 0}).sort("seen_at", -1).to_list(200)
    return items
