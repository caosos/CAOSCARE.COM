"""Facilities — multi-tenant root.

For now, owner-only. Existing single-facility data continues to work because
all `facility_id` fields are Optional in the models and queries fall back to
"all" when the field is absent. New deployments scope to a facility from
day one. Migration is opt-in: an owner can create a facility and assign
existing residents/kiosks to it via the admin UI.
"""
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException

from deps import db, require_owner, require_admin
from models import Facility, FacilityCreate, FacilityUpdate, now_utc

router = APIRouter(prefix="/facilities", tags=["facilities"])


def _iso(doc: dict) -> dict:
    for k in ("created_at",):
        v = doc.get(k)
        if v and not isinstance(v, str):
            doc[k] = v.isoformat()
    return doc


@router.get("")
async def list_facilities(user=Depends(require_admin)):
    items = await db.facilities.find({}, {"_id": 0}).sort("created_at", -1).to_list(500)
    for i in items:
        _iso(i)
    return items


@router.post("")
async def create_facility(payload: FacilityCreate, user=Depends(require_owner)):
    f = Facility(**payload.model_dump())
    doc = f.model_dump()
    doc["created_at"] = doc["created_at"].isoformat()
    await db.facilities.insert_one(doc)
    doc.pop("_id", None)
    return doc


@router.get("/{facility_id}")
async def get_facility(facility_id: str, user=Depends(require_admin)):
    f = await db.facilities.find_one({"facility_id": facility_id}, {"_id": 0})
    if not f:
        raise HTTPException(404, detail="Facility not found")
    return _iso(f)


@router.patch("/{facility_id}")
async def update_facility(facility_id: str, payload: FacilityUpdate, user=Depends(require_owner)):
    patch = {k: v for k, v in payload.model_dump(exclude_unset=True).items() if v is not None}
    if not patch:
        raise HTTPException(400, detail="Nothing to update")
    res = await db.facilities.update_one({"facility_id": facility_id}, {"$set": patch})
    if res.matched_count == 0:
        raise HTTPException(404, detail="Facility not found")
    f = await db.facilities.find_one({"facility_id": facility_id}, {"_id": 0})
    return _iso(f)


@router.delete("/{facility_id}")
async def delete_facility(facility_id: str, user=Depends(require_owner)):
    """Soft-delete: flips is_active off. Real deletion would orphan residents."""
    res = await db.facilities.update_one(
        {"facility_id": facility_id}, {"$set": {"is_active": False}},
    )
    if res.matched_count == 0:
        raise HTTPException(404, detail="Facility not found")
    return {"ok": True, "is_active": False}
