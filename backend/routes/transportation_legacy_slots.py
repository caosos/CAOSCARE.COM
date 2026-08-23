"""Legacy TransportSlot (hourly-bucket) endpoints - superseded by the
driver+vehicle TransportRun engine (transportation_engine.py) for anything
checking or making a real booking. Kept only so historical pilot-seed data
and the seed script stay readable, and so a change/cancel on an old
transport_slot_id-based request still frees its seat. Do not point new
callers (Aria, Admin, Front Desk) at anything in this file - see
routes/transportation.py's /availability/public for the live equivalent.
Split out of transportation.py to keep both under the 300-line cap.
"""
from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends

from models import TransportSlot, now_utc
from deps import db, get_current_user
from routes.realtime_facility import today_facility_date

router = APIRouter(prefix="/transportation", tags=["transportation-legacy-slots"])

DEFAULT_SLOT_HOURS = ["08:00", "09:00", "10:00", "11:00", "12:00", "13:00", "14:00", "15:00", "16:00"]


def _iso(doc: dict) -> dict:
    for k in ("created_at", "updated_at"):
        v = doc.get(k)
        if v and not isinstance(v, str):
            doc[k] = v.isoformat()
    return doc


@router.post("/slots/seed-two-weeks")
async def seed_two_weeks(user=Depends(get_current_user)):
    """Idempotent - generates 14 consecutive days of hourly slots (8am-4pm,
    capacity 1) starting today, skipping any (date, start_time) that
    already exists. Legacy TEST/DEVELOPMENT scheduling data - see the pilot
    seed script; real availability now comes from the resource engine."""
    if user.get("role") not in ("admin", "owner"):
        raise HTTPException(status_code=403, detail="Admin required")
    start = datetime.fromisoformat(today_facility_date())
    created = 0
    for day_offset in range(14):
        d = (start + timedelta(days=day_offset)).strftime("%Y-%m-%d")
        for i, start_time in enumerate(DEFAULT_SLOT_HOURS):
            end_time = DEFAULT_SLOT_HOURS[i + 1] if i + 1 < len(DEFAULT_SLOT_HOURS) else "17:00"
            existing = await db.transport_slots.find_one({"date": d, "start_time": start_time})
            if existing:
                continue
            slot = TransportSlot(date=d, start_time=start_time, end_time=end_time)
            doc = slot.model_dump()
            doc["created_at"] = doc["created_at"].isoformat()
            doc["updated_at"] = doc["updated_at"].isoformat()
            await db.transport_slots.insert_one(doc)
            created += 1
    return {"ok": True, "created": created}


@router.get("/slots")
async def list_slots(date: Optional[str] = None, user=Depends(get_current_user)):
    q = {"date": date or today_facility_date()}
    items = await db.transport_slots.find(q, {"_id": 0}).sort("start_time", 1).to_list(50)
    return [_iso(i) for i in items]


@router.get("/slots/public")
async def public_slots(date: Optional[str] = None):
    """Legacy TransportSlot view - superseded by /availability/public for
    anything checking real bookability. Kept only for historical pilot data
    / the seed script; do not point new callers at this."""
    q = {"date": date or today_facility_date()}
    items = await db.transport_slots.find(q, {"_id": 0}).sort("start_time", 1).to_list(50)
    return [
        {"start_time": i["start_time"], "end_time": i["end_time"], "open": i["booked_count"] < i["capacity"]}
        for i in items
    ]


async def release_legacy_slot(slot_id: Optional[str]) -> None:
    """Kept only so a change/cancel on a pre-resource-engine
    (transport_slot_id) booking still frees its seat. New bookings use
    transport_run_id / transportation_engine instead."""
    if not slot_id:
        return
    await db.transport_slots.update_one(
        {"slot_id": slot_id, "booked_count": {"$gt": 0}},
        {"$inc": {"booked_count": -1}, "$set": {"updated_at": now_utc().isoformat()}},
    )
