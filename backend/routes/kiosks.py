"""Kiosks + Zones CRUD."""
from fastapi import APIRouter, HTTPException, Depends
from models import Kiosk, KioskCreate, Zone, ZoneCreate
from deps import db, get_current_user

router = APIRouter(tags=["kiosks"])


# Kiosks ---------------------------------
@router.get("/kiosks")
async def list_kiosks():
    """Public list - kiosks need to self-identify without auth."""
    items = await db.kiosks.find({}, {"_id": 0}).sort("room", 1).to_list(1000)
    return items


@router.post("/kiosks")
async def create_kiosk(data: KioskCreate, user=Depends(get_current_user)):
    k = Kiosk(**data.model_dump())
    doc = k.model_dump()
    doc["created_at"] = doc["created_at"].isoformat()
    await db.kiosks.insert_one(doc)
    doc.pop("_id", None)
    return doc


@router.put("/kiosks/{kiosk_id}")
async def update_kiosk(kiosk_id: str, data: KioskCreate, user=Depends(get_current_user)):
    r = await db.kiosks.update_one({"kiosk_id": kiosk_id}, {"$set": data.model_dump()})
    if r.matched_count == 0:
        raise HTTPException(status_code=404, detail="Kiosk not found")
    doc = await db.kiosks.find_one({"kiosk_id": kiosk_id}, {"_id": 0})
    return doc


@router.delete("/kiosks/{kiosk_id}")
async def delete_kiosk(kiosk_id: str, user=Depends(get_current_user)):
    r = await db.kiosks.delete_one({"kiosk_id": kiosk_id})
    if r.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Kiosk not found")
    return {"ok": True}


# Zones ----------------------------------
@router.get("/zones")
async def list_zones():
    return await db.zones.find({}, {"_id": 0}).sort("name", 1).to_list(1000)


@router.post("/zones")
async def create_zone(data: ZoneCreate, user=Depends(get_current_user)):
    z = Zone(**data.model_dump())
    doc = z.model_dump()
    doc["created_at"] = doc["created_at"].isoformat()
    await db.zones.insert_one(doc)
    doc.pop("_id", None)
    return doc


@router.delete("/zones/{zone_id}")
async def delete_zone(zone_id: str, user=Depends(get_current_user)):
    r = await db.zones.delete_one({"zone_id": zone_id})
    if r.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Zone not found")
    return {"ok": True}
