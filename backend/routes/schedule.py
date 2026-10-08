"""Activities / daily schedule lane. Staff-typed rows are live at once;
emailed or pasted calendars (schedule_ingest.py) arrive as drafts and are
published as a batch. The public read is what residents' room screens and
Aria's get_todays_schedule tool see: published, resident-facing rows only,
in clock order. An empty list is a real, honest answer ("nothing
scheduled"), not an error. Activities or Administration staff and admins
may change the schedule (service_content_access.py).
"""
import re
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends

from models import ScheduleItem, ScheduleItemCreate, ScheduleItemUpdate, now_utc
from deps import db, get_current_user
from routes.realtime_facility import today_facility_date
from routes.content_receipts import record_content_change, staff_actor, summarize
from routes.service_content_access import SCHEDULE_DEPARTMENTS, require_content_editor

router = APIRouter(prefix="/schedule", tags=["schedule"])

# Not resident-facing: staffing notes stay on the staff view only.
_STAFF_ONLY_CATEGORIES = ["staff_hours"]
# Rows stored before the status field existed have none and were always live.
_NOT_LIVE = ["draft", "superseded"]
_TIME_RE = re.compile(r"^\s*(\d{1,2})(?::(\d{2}))?\s*([AaPp])\.?\s*[Mm]?\.?")


def time_sort_key(time_label: Optional[str]) -> tuple:
    """Clock order for free-text time labels ("9:30 AM" before "10:00 AM").
    Untimed rows (all-day notes) first; labels that aren't a clock time
    last, alphabetically - never guessed into a time."""
    if not time_label or not time_label.strip():
        return (0, 0, "")
    m = _TIME_RE.match(time_label)
    if not m:
        return (2, 0, time_label.lower())
    hour, minute = int(m.group(1)) % 12, int(m.group(2) or 0)
    if m.group(3).lower() == "p":
        hour += 12
    return (1, hour * 60 + minute, "")


def _iso(doc: dict) -> dict:
    for k in ("created_at", "updated_at", "published_at"):
        v = doc.get(k)
        if v and not isinstance(v, str):
            doc[k] = v.isoformat()
    doc.setdefault("status", "published")
    return doc


def _sorted(items: list[dict]) -> list[dict]:
    return sorted(items, key=lambda i: time_sort_key(i.get("time_label")))


async def _get(schedule_id: str) -> dict:
    existing = await db.schedule_items.find_one({"schedule_id": schedule_id}, {"_id": 0})
    if not existing:
        raise HTTPException(status_code=404, detail="Schedule item not found")
    return existing


@router.get("")
async def list_schedule(date: Optional[str] = None, user=Depends(get_current_user)):
    """Staff view - every entry for a date (default today), any status."""
    items = await db.schedule_items.find({"date": date or today_facility_date()}, {"_id": 0}).to_list(200)
    return [_iso(i) for i in _sorted(items)]


@router.get("/drafts")
async def list_drafts(user=Depends(get_current_user)):
    """Every unpublished row, any date - the review queue for emailed or
    pasted calendars."""
    items = await db.schedule_items.find({"status": "draft"}, {"_id": 0}).sort("date", 1).to_list(500)
    return [_iso(i) for i in items]


@router.post("")
async def create_schedule_item(data: ScheduleItemCreate, user=Depends(get_current_user)):
    require_content_editor(user, SCHEDULE_DEPARTMENTS)
    now = now_utc()
    item = ScheduleItem(**data.model_dump(), created_by=user["user_id"],
                        published_by=user["user_id"], published_at=now)
    doc = item.model_dump()
    for k in ("created_at", "updated_at", "published_at"):
        doc[k] = doc[k].isoformat()
    await db.schedule_items.insert_one(doc)
    doc.pop("_id", None)
    await record_content_change(kind="schedule", action="created", object_type="schedule_item",
                                object_id=doc["schedule_id"], actor=staff_actor(user),
                                after=summarize("schedule", doc))
    return doc


@router.patch("/{schedule_id}")
async def update_schedule_item(schedule_id: str, data: ScheduleItemUpdate, user=Depends(get_current_user)):
    """A correction. A published row stays published (the editor is the
    reviewer) and residents see the change on their next read."""
    require_content_editor(user, SCHEDULE_DEPARTMENTS)
    existing = await _get(schedule_id)
    if existing.get("status") == "superseded":
        raise HTTPException(status_code=409, detail="This entry was replaced by a newer calendar; edit the current entry instead")
    patch = {k: v for k, v in data.model_dump(exclude_none=True).items()}
    patch["updated_at"] = now_utc().isoformat()
    await db.schedule_items.update_one({"schedule_id": schedule_id}, {"$set": patch})
    updated = await _get(schedule_id)
    await record_content_change(kind="schedule", action="edited", object_type="schedule_item",
                                object_id=schedule_id, actor=staff_actor(user), ingest_id=updated.get("ingest_id"),
                                before=summarize("schedule", existing), after=summarize("schedule", updated))
    return _iso(updated)


@router.post("/{schedule_id}/publish")
async def publish_schedule_item(schedule_id: str, user=Depends(get_current_user)):
    require_content_editor(user, SCHEDULE_DEPARTMENTS)
    existing = await _get(schedule_id)
    if existing.get("status") == "superseded":
        raise HTTPException(status_code=409, detail="This entry was replaced by a newer calendar and cannot be published again")
    now_iso = now_utc().isoformat()
    await db.schedule_items.update_one({"schedule_id": schedule_id}, {"$set": {
        "status": "published", "published_by": user["user_id"], "published_at": now_iso, "updated_at": now_iso,
    }})
    updated = await _get(schedule_id)
    await record_content_change(kind="schedule", action="published", object_type="schedule_item",
                                object_id=schedule_id, actor=staff_actor(user), ingest_id=updated.get("ingest_id"),
                                before=summarize("schedule", existing), after=summarize("schedule", updated))
    return _iso(updated)


@router.post("/batches/{ingest_id}/publish")
async def publish_batch(ingest_id: str, user=Depends(get_current_user)):
    """Publish every draft one emailed/pasted calendar produced. A newer
    calendar replaces the earlier emailed/pasted rows for the same dates
    (status -> "superseded", kept for history) so residents never see an
    old and a corrected calendar side by side. Staff-typed rows are
    never replaced by an ingest."""
    require_content_editor(user, SCHEDULE_DEPARTMENTS)
    drafts = await db.schedule_items.find({"ingest_id": ingest_id, "status": "draft"}, {"_id": 0}).to_list(500)
    if not drafts:
        raise HTTPException(status_code=404, detail="No unpublished entries for this calendar")
    now_iso = now_utc().isoformat()
    dates = sorted({d["date"] for d in drafts})
    replace_q = {"date": {"$in": dates}, "ingest_id": {"$nin": [None, ingest_id]},
                 "status": {"$nin": _NOT_LIVE}}
    old_rows = await db.schedule_items.find(replace_q, {"_id": 0}).to_list(500)
    replaced = await db.schedule_items.update_many(
        replace_q, {"$set": {"status": "superseded", "updated_at": now_iso}},
    )
    await db.schedule_items.update_many(
        {"ingest_id": ingest_id, "status": "draft"},
        {"$set": {"status": "published", "published_by": user["user_id"], "published_at": now_iso, "updated_at": now_iso}},
    )
    actor = staff_actor(user)
    await record_content_change(
        kind="schedule", action="published", object_type="schedule_batch", object_id=ingest_id,
        actor=actor, ingest_id=ingest_id, before={"status": "draft", "item_count": len(drafts)},
        after={"status": "published", "dates": dates, "published_count": len(drafts),
               "superseded_schedule_ids": [o["schedule_id"] for o in old_rows]})
    for old in old_rows:
        await record_content_change(
            kind="schedule", action="superseded", object_type="schedule_item", object_id=old["schedule_id"],
            actor=actor, ingest_id=ingest_id, before=summarize("schedule", old),
            after={"status": "superseded", "replaced_by_ingest": ingest_id})
    return {"ingest_id": ingest_id, "published_count": len(drafts), "dates": dates,
            "replaced_count": replaced.modified_count}


@router.delete("/{schedule_id}")
async def delete_schedule_item(schedule_id: str, user=Depends(get_current_user)):
    require_content_editor(user, SCHEDULE_DEPARTMENTS)
    existing = await db.schedule_items.find_one({"schedule_id": schedule_id}, {"_id": 0})
    r = await db.schedule_items.delete_one({"schedule_id": schedule_id})
    if r.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Schedule item not found")
    await record_content_change(kind="schedule", action="deleted", object_type="schedule_item",
                                object_id=schedule_id, actor=staff_actor(user),
                                ingest_id=(existing or {}).get("ingest_id"), before=summarize("schedule", existing))
    return {"ok": True}


@router.get("/public/today")
async def public_today(date: Optional[str] = None, category: Optional[str] = None):
    """No auth - same public trust model as the other resident-facing
    read endpoints Aria calls live. Published, resident-facing rows only,
    in clock order."""
    q: dict = {"date": date or today_facility_date(), "status": {"$nin": _NOT_LIVE},
               "category": {"$nin": _STAFF_ONLY_CATEGORIES}}
    if category:
        if category in _STAFF_ONLY_CATEGORIES:
            return []
        q["category"] = category
    items = await db.schedule_items.find(q, {"_id": 0}).to_list(200)
    return [
        {
            "time_label": i.get("time_label"),
            "title": i["title"],
            "description": i.get("description") or "",
            "category": i["category"],
        }
        for i in _sorted(items)
    ]
