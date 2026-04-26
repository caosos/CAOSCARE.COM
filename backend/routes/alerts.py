"""Alerts routes - create from kiosk, list/acknowledge/resolve for staff."""
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends, Query
from models import Alert, AlertCreate, AlertClose, now_utc
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

    # Fan out family notifications (best-effort — log failures instead of silently swallowing)
    try:
        from routes.notifications import notify_family_for_alert
        await notify_family_for_alert(doc)
    except Exception as e:
        import logging
        logging.warning(f"Family notification fan-out failed for alert {doc.get('alert_id')}: {e}")

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
    """Active + recently acknowledged for live staff dashboard, with lazy escalation."""
    items = (
        await db.alerts.find(
            {"status": {"$in": ["active", "acknowledged"]}},
            {"_id": 0},
        )
        .sort("created_at", -1)
        .to_list(200)
    )
    # Escalation thresholds (seconds since created, while still active)
    ESCALATION = [
        (60, 1),   # after 1 min unacked -> level 1
        (180, 2),  # after 3 min unacked -> level 2 (supervisor)
        (420, 3),  # after 7 min unacked -> level 3 (code)
    ]
    now_ts = datetime.now(timezone.utc)

    for it in items:
        it["created_at"] = _iso(it.get("created_at"))
        it["acknowledged_at"] = _iso(it.get("acknowledged_at"))
        it["resolved_at"] = _iso(it.get("resolved_at"))

        if it.get("status") == "active":
            try:
                created = datetime.fromisoformat(it["created_at"])
            except Exception:
                continue
            if created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)
            age = (now_ts - created).total_seconds()
            new_level = 0
            for threshold, level in ESCALATION:
                if age >= threshold:
                    new_level = level
            if new_level > (it.get("escalation_level") or 0):
                it["escalation_level"] = new_level
                await db.alerts.update_one(
                    {"alert_id": it["alert_id"]},
                    {"$set": {"escalation_level": new_level}},
                )
    return items


@router.post("/{alert_id}/acknowledge")
async def acknowledge(alert_id: str, user=Depends(get_current_user)):
    now_dt = now_utc()
    now = now_dt.isoformat()
    existing = await db.alerts.find_one({"alert_id": alert_id}, {"_id": 0})
    update = {"status": "acknowledged", "acknowledged_by": user["name"], "acknowledged_at": now}
    if existing and existing.get("created_at"):
        try:
            created = datetime.fromisoformat(existing["created_at"]) if isinstance(existing["created_at"], str) else existing["created_at"]
            if created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)
            update["response_seconds"] = int((now_dt - created).total_seconds())
        except Exception:
            pass
    r = await db.alerts.update_one(
        {"alert_id": alert_id, "status": "active"},
        {"$set": update},
    )
    if r.matched_count == 0:
        raise HTTPException(status_code=404, detail="Alert not active or not found")
    doc = await db.alerts.find_one({"alert_id": alert_id}, {"_id": 0})
    return doc


@router.post("/{alert_id}/resolve")
async def resolve(alert_id: str, user=Depends(get_current_user)):
    now_dt = now_utc()
    now = now_dt.isoformat()
    existing = await db.alerts.find_one({"alert_id": alert_id}, {"_id": 0})
    update = {"status": "resolved", "resolved_by": user["name"], "resolved_at": now}
    if existing:
        anchor = existing.get("acknowledged_at") or existing.get("created_at")
        if anchor:
            try:
                anc = datetime.fromisoformat(anchor) if isinstance(anchor, str) else anchor
                if anc.tzinfo is None:
                    anc = anc.replace(tzinfo=timezone.utc)
                update["duration_seconds"] = int((now_dt - anc).total_seconds())
            except Exception:
                pass
    r = await db.alerts.update_one(
        {"alert_id": alert_id, "status": {"$in": ["active", "acknowledged"]}},
        {"$set": update},
    )
    if r.matched_count == 0:
        raise HTTPException(status_code=404, detail="Alert not found")
    doc = await db.alerts.find_one({"alert_id": alert_id}, {"_id": 0})
    return doc


@router.post("/{alert_id}/close")
async def close_alert(alert_id: str, data: AlertClose, user=Depends(get_current_user)):
    """Resolve + capture outcome, category, and close-out notes (operational truth)."""
    now_dt = now_utc()
    now = now_dt.isoformat()
    existing = await db.alerts.find_one({"alert_id": alert_id}, {"_id": 0})
    update = {
        "status": "resolved",
        "resolved_by": user["name"],
        "resolved_at": now,
        "outcome": data.outcome,
        "close_notes": data.close_notes or "",
    }
    if data.category:
        update["category"] = data.category
    if existing:
        anchor = existing.get("acknowledged_at") or existing.get("created_at")
        if anchor:
            try:
                anc = datetime.fromisoformat(anchor) if isinstance(anchor, str) else anchor
                if anc.tzinfo is None:
                    anc = anc.replace(tzinfo=timezone.utc)
                update["duration_seconds"] = int((now_dt - anc).total_seconds())
            except Exception:
                pass
    r = await db.alerts.update_one(
        {"alert_id": alert_id, "status": {"$in": ["active", "acknowledged", "resolved"]}},
        {"$set": update},
    )
    if r.matched_count == 0:
        raise HTTPException(status_code=404, detail="Alert not found")
    doc = await db.alerts.find_one({"alert_id": alert_id}, {"_id": 0})
    for k in ("created_at", "acknowledged_at", "resolved_at"):
        if doc.get(k) and not isinstance(doc[k], str):
            doc[k] = doc[k].isoformat()

    # Auto-classify the category + AI summary if not set by staff
    try:
        from routes.ai import classify_alert_background
        import asyncio
        if not doc.get("category") or not doc.get("ai_summary"):
            asyncio.create_task(classify_alert_background(doc["alert_id"]))
    except Exception:
        pass

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


@router.get("/public/{alert_id}/status")
async def public_alert_status(alert_id: str):
    """Kiosk (no login) polls this every 4s to detect when staff resolves the
    call. Intentionally minimal — no PII, no chat content — so it can sit
    behind a public route without leaking resident info."""
    doc = await db.alerts.find_one(
        {"alert_id": alert_id},
        {"_id": 0, "alert_id": 1, "status": 1, "severity": 1},
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Alert not found")
    return doc


@router.get("/{alert_id}")
async def get_alert(alert_id: str, user=Depends(get_current_user)):
    """Full event timeline for one alert (created → paged → acked → resolved)."""
    doc = await db.alerts.find_one({"alert_id": alert_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Alert not found")
    for k in ("created_at", "acknowledged_at", "resolved_at"):
        if doc.get(k) and not isinstance(doc[k], str):
            doc[k] = doc[k].isoformat()

    timeline = []
    timeline.append({"at": doc["created_at"], "label": "Created", "detail": f"via {doc.get('triggered_by', 'unknown')}"})
    if doc.get("escalation_level"):
        timeline.append({
            "at": doc["created_at"],
            "label": f"Escalation level {doc['escalation_level']}",
            "detail": "Auto-escalated — unacknowledged",
        })
    if doc.get("acknowledged_at"):
        timeline.append({
            "at": doc["acknowledged_at"],
            "label": "Acknowledged",
            "detail": f"by {doc.get('acknowledged_by', 'staff')}",
        })
    if doc.get("resolved_at"):
        timeline.append({
            "at": doc["resolved_at"],
            "label": "Resolved",
            "detail": f"by {doc.get('resolved_by', 'staff')}" + (f" — {doc['outcome']}" if doc.get("outcome") else ""),
        })

    chat = []
    if doc.get("resident_id"):
        chat = await db.chat_messages.find(
            {"resident_id": doc["resident_id"]},
            {"_id": 0},
        ).sort("created_at", -1).to_list(20)
        for m in chat:
            if m.get("created_at") and not isinstance(m["created_at"], str):
                m["created_at"] = m["created_at"].isoformat()
        chat.reverse()

    return {"alert": doc, "timeline": timeline, "chat": chat}
