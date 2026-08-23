"""Schedule/activities lane (Terminal 8, lowest-stakes of the three planned
inbound lanes). Staff-entered for now - no email/calendar dependency to
ship. Public read endpoint lets Aria/the kiosk answer "what's happening
today" honestly from a real structured source instead of guessing; admin
routes let staff maintain it. No request, no receipt, no routing - this is
a read lane only.
"""
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends

from models import ScheduleItem, ScheduleItemCreate, ScheduleItemUpdate, now_utc
from deps import db, get_current_user
from routes.realtime_facility import today_facility_date

router = APIRouter(prefix="/schedule", tags=["schedule"])


def _iso(doc: dict) -> dict:
    for k in ("created_at", "updated_at"):
        v = doc.get(k)
        if v and not isinstance(v, str):
            doc[k] = v.isoformat()
    return doc


@router.get("")
async def list_schedule(date: Optional[str] = None, user=Depends(get_current_user)):
    """Admin/staff view - all entries for a date (default today), any category."""
    q = {"date": date or today_facility_date()}
    items = await db.schedule_items.find(q, {"_id": 0}).sort("time_label", 1).to_list(200)
    return [_iso(i) for i in items]


@router.post("")
async def create_schedule_item(data: ScheduleItemCreate, user=Depends(get_current_user)):
    if user.get("role") not in ("admin", "owner", "staff"):
        raise HTTPException(status_code=403, detail="Staff required")
    item = ScheduleItem(**data.model_dump(), created_by=user["user_id"])
    doc = item.model_dump()
    doc["created_at"] = doc["created_at"].isoformat()
    doc["updated_at"] = doc["updated_at"].isoformat()
    await db.schedule_items.insert_one(doc)
    doc.pop("_id", None)
    return doc


@router.patch("/{schedule_id}")
async def update_schedule_item(schedule_id: str, data: ScheduleItemUpdate, user=Depends(get_current_user)):
    if user.get("role") not in ("admin", "owner", "staff"):
        raise HTTPException(status_code=403, detail="Staff required")
    existing = await db.schedule_items.find_one({"schedule_id": schedule_id}, {"_id": 0})
    if not existing:
        raise HTTPException(status_code=404, detail="Schedule item not found")
    patch = {k: v for k, v in data.model_dump(exclude_none=True).items()}
    patch["updated_at"] = now_utc().isoformat()
    await db.schedule_items.update_one({"schedule_id": schedule_id}, {"$set": patch})
    return _iso(await db.schedule_items.find_one({"schedule_id": schedule_id}, {"_id": 0}))


@router.delete("/{schedule_id}")
async def delete_schedule_item(schedule_id: str, user=Depends(get_current_user)):
    if user.get("role") not in ("admin", "owner", "staff"):
        raise HTTPException(status_code=403, detail="Staff required")
    r = await db.schedule_items.delete_one({"schedule_id": schedule_id})
    if r.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Schedule item not found")
    return {"ok": True}


@router.get("/public/today")
async def public_today(date: Optional[str] = None, category: Optional[str] = None):
    """No auth - same public trust model as the other resident-facing
    read/request endpoints Aria calls live. Returns only what's actually on
    file; an empty list is a real, honest answer ("nothing scheduled"), not
    an error."""
    q: dict = {"date": date or today_facility_date()}
    if category:
        q["category"] = category
    items = await db.schedule_items.find(q, {"_id": 0}).sort("time_label", 1).to_list(200)
    return [
        {
            "time_label": i.get("time_label"),
            "title": i["title"],
            "description": i.get("description") or "",
            "category": i["category"],
        }
        for i in items
    ]
