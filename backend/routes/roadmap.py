"""Roadmap / phase checklist - admins track which blueprint items are live."""
from fastapi import APIRouter, HTTPException, Depends
from datetime import datetime, timezone
from models import RoadmapItem, RoadmapItemUpdate, now_utc
from deps import db, get_current_user

router = APIRouter(prefix="/roadmap", tags=["roadmap"])


@router.get("")
async def list_roadmap():
    """Public: anyone can see roadmap progress."""
    items = await db.roadmap.find({}, {"_id": 0}).sort([("phase", 1), ("order", 1)]).to_list(500)
    for it in items:
        for k in ("created_at", "updated_at"):
            v = it.get(k)
            if v and not isinstance(v, str):
                it[k] = v.isoformat()
    return items


@router.patch("/{item_id}")
async def update_item(item_id: str, data: RoadmapItemUpdate, user=Depends(get_current_user)):
    upd = {k: v for k, v in data.model_dump().items() if v is not None}
    if not upd:
        raise HTTPException(status_code=400, detail="Nothing to update")
    upd["updated_at"] = now_utc().isoformat()
    r = await db.roadmap.update_one({"item_id": item_id}, {"$set": upd})
    if r.matched_count == 0:
        raise HTTPException(status_code=404, detail="Item not found")
    doc = await db.roadmap.find_one({"item_id": item_id}, {"_id": 0})
    return doc


@router.get("/progress")
async def progress():
    """Aggregate progress per phase."""
    pipeline = [
        {"$group": {
            "_id": {"phase": "$phase", "status": "$status"},
            "count": {"$sum": 1},
        }},
    ]
    rows = await db.roadmap.aggregate(pipeline).to_list(100)
    out = {}
    for row in rows:
        p = row["_id"]["phase"]
        s = row["_id"]["status"]
        out.setdefault(p, {"done": 0, "in_progress": 0, "not_started": 0, "blocked": 0})
        out[p][s] = row["count"]
    return out
