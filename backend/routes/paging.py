"""Pager RF emulation — bridge the facility's existing paging transmitter (or any
external paging system) into CAOS Care. Incoming page events are mirrored onto
every staff tablet in real time.

Wiring guide:
  - A cheap RS-232 / USB capture on the facility pager transmitter, or an
    existing SDK hook, POSTs each page to /api/paging/event.
  - Staff tablets poll /api/paging/feed every 3s and render the banner.
  - Pages are short-lived: anything older than 30 minutes is filtered out of
    the feed but retained for audit.
"""
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel
from typing import Optional, Literal
from deps import db, get_current_user
from models import now_utc, uid

router = APIRouter(prefix="/paging", tags=["paging"])


class PagerEventInput(BaseModel):
    """POST body from the facility pager bridge (or the admin test button)."""
    source: Literal["facility_rf", "cap_code", "sim", "caos"] = "facility_rf"
    cap_code: Optional[str] = None                       # pager cap code / address
    resident_id: Optional[str] = None
    room: Optional[str] = None
    zone: Optional[str] = None
    message: str
    urgency: Literal["info", "page", "stat", "code"] = "page"


@router.post("/event")
async def pager_event(evt: PagerEventInput, request: Request):
    """Public + HMAC-optional. Pager bridge posts here."""
    from routes.device_auth import verify_device_token
    await verify_device_token(request, "locations.ingest")

    # Try to enrich: cap_code → resident
    resident_name = None
    if evt.cap_code and not evt.resident_id:
        r = await db.residents.find_one({"pendant_id": evt.cap_code}, {"_id": 0})
        if r:
            evt.resident_id = r["resident_id"]
            evt.room = evt.room or r.get("room")
    if evt.resident_id:
        r = await db.residents.find_one({"resident_id": evt.resident_id}, {"_id": 0, "name": 1, "room": 1})
        if r:
            resident_name = r["name"]
            evt.room = evt.room or r.get("room")

    doc = {
        "page_id": uid("page"),
        "source": evt.source,
        "cap_code": evt.cap_code,
        "resident_id": evt.resident_id,
        "resident_name": resident_name,
        "room": evt.room,
        "zone": evt.zone,
        "message": evt.message[:500],
        "urgency": evt.urgency,
        "created_at": now_utc().isoformat(),
    }
    await db.pager_events.insert_one(doc)
    doc.pop("_id", None)
    return doc


@router.get("/feed")
async def feed(user=Depends(get_current_user), minutes: int = 30, limit: int = 50):
    cutoff = (now_utc() - timedelta(minutes=minutes)).isoformat()
    items = await db.pager_events.find(
        {"created_at": {"$gte": cutoff}}, {"_id": 0},
    ).sort("created_at", -1).to_list(limit)
    return items


@router.post("/simulate")
async def simulate(evt: PagerEventInput, user=Depends(get_current_user)):
    """Admin-only — push a test page to all staff tablets for the demo."""
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin required")
    resident_name = None
    if evt.resident_id:
        r = await db.residents.find_one({"resident_id": evt.resident_id}, {"_id": 0, "name": 1, "room": 1})
        if r:
            resident_name = r["name"]
            evt.room = evt.room or r.get("room")
    doc = {
        "page_id": uid("page"),
        "source": "sim",
        "cap_code": evt.cap_code,
        "resident_id": evt.resident_id,
        "resident_name": resident_name,
        "room": evt.room,
        "zone": evt.zone,
        "message": evt.message[:500],
        "urgency": evt.urgency,
        "created_at": now_utc().isoformat(),
    }
    await db.pager_events.insert_one(doc)
    doc.pop("_id", None)
    return doc
