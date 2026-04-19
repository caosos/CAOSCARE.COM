"""Wearables - CRUD + public event ingest (smartwatches, earbuds, BLE beacons, etc)."""
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Depends, Request
from models import Wearable, WearableCreate, WearableEventInput, Alert, now_utc
from deps import db, get_current_user

router = APIRouter(prefix="/wearables", tags=["wearables"])


def _iso(doc: dict) -> dict:
    for k in ("created_at", "last_seen_at"):
        v = doc.get(k)
        if v and not isinstance(v, str):
            doc[k] = v.isoformat()
    return doc


@router.get("")
async def list_wearables(user=Depends(get_current_user)):
    items = await db.wearables.find({}, {"_id": 0}).sort("device_label", 1).to_list(1000)
    for w in items:
        _iso(w)
        if w.get("resident_id"):
            r = await db.residents.find_one({"resident_id": w["resident_id"]}, {"_id": 0, "name": 1, "room": 1})
            if r:
                w["resident_name"] = r.get("name")
                w["room"] = r.get("room")
    return items


@router.post("")
async def create_wearable(data: WearableCreate, user=Depends(get_current_user)):
    if data.mac_address:
        existing = await db.wearables.find_one({"mac_address": data.mac_address}, {"_id": 0})
        if existing:
            raise HTTPException(status_code=400, detail="MAC address already registered")
    w = Wearable(**data.model_dump())
    doc = w.model_dump()
    doc["created_at"] = doc["created_at"].isoformat()
    doc["last_seen_at"] = None
    await db.wearables.insert_one(doc)
    doc.pop("_id", None)
    return doc


@router.put("/{wearable_id}")
async def update_wearable(wearable_id: str, data: WearableCreate, user=Depends(get_current_user)):
    r = await db.wearables.update_one({"wearable_id": wearable_id}, {"$set": data.model_dump()})
    if r.matched_count == 0:
        raise HTTPException(status_code=404, detail="Wearable not found")
    doc = await db.wearables.find_one({"wearable_id": wearable_id}, {"_id": 0})
    return _iso(doc)


@router.delete("/{wearable_id}")
async def delete_wearable(wearable_id: str, user=Depends(get_current_user)):
    r = await db.wearables.delete_one({"wearable_id": wearable_id})
    if r.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Wearable not found")
    return {"ok": True}


@router.post("/event")
async def wearable_event(evt: WearableEventInput, request: Request):
    """Public ingest. The companion phone / watch / beacon POSTs here when something happens."""
    from routes.device_auth import verify_device_token
    await verify_device_token(request, "wearables.event")

    query = {}
    if evt.wearable_id:
        query["wearable_id"] = evt.wearable_id
    elif evt.mac_address:
        query["mac_address"] = evt.mac_address
    else:
        raise HTTPException(status_code=400, detail="wearable_id or mac_address required")

    wearable = await db.wearables.find_one(query, {"_id": 0})
    if not wearable:
        raise HTTPException(status_code=404, detail="Wearable not registered")

    # Update telemetry
    update = {"last_seen_at": now_utc().isoformat()}
    if evt.heart_rate is not None:
        update["last_heart_rate"] = evt.heart_rate
    if evt.battery_percent is not None:
        update["battery_percent"] = evt.battery_percent
        if evt.battery_percent < 15 and wearable.get("status") == "active":
            update["status"] = "low_battery"
    await db.wearables.update_one({"wearable_id": wearable["wearable_id"]}, {"$set": update})

    # Record location ping if zone provided
    if evt.zone and wearable.get("resident_id"):
        loc_doc = {
            "update_id": f"loc_{datetime.now(timezone.utc).timestamp()}",
            "resident_id": wearable["resident_id"],
            "zone": evt.zone,
            "signal_strength": evt.signal_strength,
            "source": "wearable",
            "created_at": now_utc().isoformat(),
        }
        await db.locations.insert_one(loc_doc)
        loc_doc.pop("_id", None)

    # No alert for periodic pings or plain inactivity
    if evt.event_type in ("periodic_ping",):
        return {"ok": True, "wearable": wearable["wearable_id"], "alert": None}

    # Create alert
    resident_name = None
    room = None
    if wearable.get("resident_id"):
        r = await db.residents.find_one({"resident_id": wearable["resident_id"]}, {"_id": 0})
        if r:
            resident_name = r["name"]
            room = r.get("room")

    severity_map = {
        "press": "assist",
        "fall": "emergency",
        "heart_rate_high": "emergency",
        "heart_rate_low": "emergency",
        "inactivity": "assist",
    }
    severity = severity_map.get(evt.event_type, "assist")
    msg = f"Wearable {evt.event_type.replace('_', ' ')}"
    if evt.heart_rate:
        msg += f" · HR {evt.heart_rate}"

    alert = Alert(
        resident_id=wearable.get("resident_id"),
        resident_name=resident_name,
        room=room,
        zone=evt.zone,
        severity=severity,
        message=msg,
        triggered_by="wearable",
    )
    doc = alert.model_dump()
    doc["created_at"] = doc["created_at"].isoformat()
    doc["acknowledged_at"] = None
    doc["resolved_at"] = None
    await db.alerts.insert_one(doc)
    doc.pop("_id", None)

    # Family fan-out
    try:
        from routes.notifications import notify_family_for_alert
        await notify_family_for_alert(doc)
    except Exception as e:
        import logging
        logging.warning(f"Family fan-out failed for wearable alert: {e}")

    return {"ok": True, "wearable": wearable["wearable_id"], "alert": doc}
