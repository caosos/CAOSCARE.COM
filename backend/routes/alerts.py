"""Alerts routes - create from kiosk, list/acknowledge/resolve for staff."""
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends, Query
from models import Alert, AlertCreate, now_utc
from deps import db, get_current_user

router = APIRouter(prefix="/alerts", tags=["alerts"])


def _iso(dt):
    if dt is None:
        return None
    if isinstance(dt, str):
        return dt
    return dt.isoformat()


@router.post("")
async def create_alert(data: AlertCreate):
    """Public endpoint - kiosks trigger this when resident presses the emergency button."""
    kiosk = None
    resident = None
    room = None
    zone = None
    resident_name = None

    if data.kiosk_id:
        kiosk = await db.kiosks.find_one({"kiosk_id": data.kiosk_id}, {"_id": 0})
        if kiosk:
            room = kiosk.get("room")
            zone = kiosk.get("zone")

    rid = data.resident_id
    if not rid and room:
        r = await db.residents.find_one({"room": room}, {"_id": 0})
        if r:
            rid = r["resident_id"]
            resident_name = r["name"]
    elif rid:
        r = await db.residents.find_one({"resident_id": rid}, {"_id": 0})
        if r:
            resident_name = r["name"]
            if not room:
                room = r.get("room")

    # Latest location for resident (may refine zone)
    if rid:
        latest = await db.locations.find_one({"resident_id": rid}, {"_id": 0}, sort=[("created_at", -1)])
        if latest and latest.get("zone"):
            zone = latest["zone"]

    alert = Alert(
        kiosk_id=data.kiosk_id,
        resident_id=rid,
        resident_name=resident_name,
        room=room,
        zone=zone,
        severity=data.severity,
        message=data.message,
        triggered_by=data.triggered_by,
    )
    doc = alert.model_dump()
    doc["created_at"] = doc["created_at"].isoformat()
    doc["acknowledged_at"] = None
    doc["resolved_at"] = None
    await db.alerts.insert_one(doc)
    doc.pop("_id", None)
    return doc


@router.get("")
async def list_alerts(
    status: Optional[str] = Query(None),
    limit: int = 100,
    user=Depends(get_current_user),
):
    q = {}
    if status:
        q["status"] = status
    items = (
        await db.alerts.find(q, {"_id": 0})
        .sort("created_at", -1)
        .to_list(limit)
    )
    for it in items:
        it["created_at"] = _iso(it.get("created_at"))
        it["acknowledged_at"] = _iso(it.get("acknowledged_at"))
        it["resolved_at"] = _iso(it.get("resolved_at"))
    return items


@router.get("/feed")
async def alerts_feed(user=Depends(get_current_user)):
    """Active + recently acknowledged for live staff dashboard."""
    items = (
        await db.alerts.find(
            {"status": {"$in": ["active", "acknowledged"]}},
            {"_id": 0},
        )
        .sort("created_at", -1)
        .to_list(200)
    )
    for it in items:
        it["created_at"] = _iso(it.get("created_at"))
        it["acknowledged_at"] = _iso(it.get("acknowledged_at"))
        it["resolved_at"] = _iso(it.get("resolved_at"))
    return items


@router.post("/{alert_id}/acknowledge")
async def acknowledge(alert_id: str, user=Depends(get_current_user)):
    now = now_utc().isoformat()
    r = await db.alerts.update_one(
        {"alert_id": alert_id, "status": "active"},
        {"$set": {"status": "acknowledged", "acknowledged_by": user["name"], "acknowledged_at": now}},
    )
    if r.matched_count == 0:
        raise HTTPException(status_code=404, detail="Alert not active or not found")
    doc = await db.alerts.find_one({"alert_id": alert_id}, {"_id": 0})
    return doc


@router.post("/{alert_id}/resolve")
async def resolve(alert_id: str, user=Depends(get_current_user)):
    now = now_utc().isoformat()
    r = await db.alerts.update_one(
        {"alert_id": alert_id, "status": {"$in": ["active", "acknowledged"]}},
        {"$set": {"status": "resolved", "resolved_by": user["name"], "resolved_at": now}},
    )
    if r.matched_count == 0:
        raise HTTPException(status_code=404, detail="Alert not found")
    doc = await db.alerts.find_one({"alert_id": alert_id}, {"_id": 0})
    return doc


@router.get("/stats")
async def alert_stats(user=Depends(get_current_user)):
    active = await db.alerts.count_documents({"status": "active"})
    ack = await db.alerts.count_documents({"status": "acknowledged"})
    resolved_today_ct = 0
    # count resolved in last 24h
    from datetime import timedelta
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
    resolved_today_ct = await db.alerts.count_documents(
        {"status": "resolved", "resolved_at": {"$gte": cutoff}}
    )
    emergency_active = await db.alerts.count_documents(
        {"status": "active", "severity": "emergency"}
    )
    return {
        "active": active,
        "acknowledged": ack,
        "resolved_24h": resolved_today_ct,
        "emergency_active": emergency_active,
    }
