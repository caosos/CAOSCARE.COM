"""Residents CRUD."""
from fastapi import APIRouter, HTTPException, Depends
from typing import List
from models import Resident, ResidentCreate
from deps import db, get_current_user

router = APIRouter(prefix="/residents", tags=["residents"])


def _serialize(doc: dict) -> dict:
    if isinstance(doc.get("created_at"), str):
        return doc
    doc = {**doc}
    ca = doc.get("created_at")
    if hasattr(ca, "isoformat"):
        doc["created_at"] = ca.isoformat()
    return doc


@router.get("")
async def list_residents(user=Depends(get_current_user)):
    items = await db.residents.find({}, {"_id": 0}).sort("name", 1).to_list(1000)
    return items


@router.post("")
async def create_resident(data: ResidentCreate, user=Depends(get_current_user)):
    resident = Resident(**data.model_dump())
    doc = resident.model_dump()
    doc["created_at"] = doc["created_at"].isoformat()
    await db.residents.insert_one(doc)
    doc.pop("_id", None)
    return doc


@router.get("/{resident_id}")
async def get_resident(resident_id: str, user=Depends(get_current_user)):
    doc = await db.residents.find_one({"resident_id": resident_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Resident not found")
    return doc


@router.put("/{resident_id}")
async def update_resident(resident_id: str, data: ResidentCreate, user=Depends(get_current_user)):
    upd = data.model_dump()
    r = await db.residents.update_one({"resident_id": resident_id}, {"$set": upd})
    if r.matched_count == 0:
        raise HTTPException(status_code=404, detail="Resident not found")
    doc = await db.residents.find_one({"resident_id": resident_id}, {"_id": 0})
    return doc


@router.delete("/{resident_id}")
async def delete_resident(resident_id: str, user=Depends(get_current_user)):
    r = await db.residents.delete_one({"resident_id": resident_id})
    if r.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Resident not found")
    return {"ok": True}


@router.get("/public/by-kiosk/{kiosk_id}")
async def resident_by_kiosk(kiosk_id: str):
    """Public endpoint used by kiosks to look up the resident tied to their room."""
    kiosk = await db.kiosks.find_one({"kiosk_id": kiosk_id}, {"_id": 0})
    if not kiosk:
        raise HTTPException(status_code=404, detail="Kiosk not found")
    resident = await db.residents.find_one({"room": kiosk["room"]}, {"_id": 0})
    return {"kiosk": kiosk, "resident": resident}


@router.get("/{resident_id}/movement")
async def resident_movement(resident_id: str, hours: int = 24, user=Depends(get_current_user)):
    """Zone-visit timeline for a resident over the last N hours."""
    from datetime import datetime, timezone, timedelta
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    locs = await db.locations.find(
        {"resident_id": resident_id, "created_at": {"$gte": cutoff}},
        {"_id": 0},
    ).sort("created_at", 1).to_list(5000)
    # Collapse consecutive pings in the same zone into a "visit"
    visits = []
    for l in locs:
        if visits and visits[-1]["zone"] == l["zone"]:
            visits[-1]["until"] = l["created_at"]
            visits[-1]["pings"] += 1
        else:
            visits.append({
                "zone": l["zone"],
                "from": l["created_at"],
                "until": l["created_at"],
                "pings": 1,
                "source": l.get("source"),
            })
    return {"visits": visits, "total_pings": len(locs)}
