"""Transportation resource config - drivers, vehicles, scheduling buffer.
Admin-only (this is facility configuration, not day-to-day coordination -
Front Desk reads the calendar, it doesn't edit the fleet). Split out of
transportation.py to keep both under the 300-line cap.
"""
from fastapi import APIRouter, HTTPException, Depends

from deps import db, require_admin
from models import now_utc
from models_transportation import (
    TransportDriver, TransportDriverCreate, TransportDriverUpdate,
    TransportVehicle, TransportVehicleCreate, TransportVehicleUpdate,
    TransportSchedulingConfigUpdate,
)
from transportation_engine import get_scheduling_config

router = APIRouter(prefix="/transportation", tags=["transportation-resources"])


@router.get("/drivers")
async def list_drivers(user=Depends(require_admin)):
    return await db.transport_drivers.find({}, {"_id": 0}).sort("name", 1).to_list(50)


@router.post("/drivers")
async def create_driver(data: TransportDriverCreate, user=Depends(require_admin)):
    driver = TransportDriver(**data.model_dump())
    doc = driver.model_dump()
    doc["created_at"] = doc["created_at"].isoformat()
    await db.transport_drivers.insert_one({**doc})
    doc.pop("_id", None)
    return doc


@router.patch("/drivers/{driver_id}")
async def update_driver(driver_id: str, data: TransportDriverUpdate, user=Depends(require_admin)):
    patch = {k: v for k, v in data.model_dump().items() if v is not None}
    r = await db.transport_drivers.update_one({"driver_id": driver_id}, {"$set": patch})
    if r.matched_count == 0:
        raise HTTPException(status_code=404, detail="Driver not found")
    return await db.transport_drivers.find_one({"driver_id": driver_id}, {"_id": 0})


@router.delete("/drivers/{driver_id}")
async def delete_driver(driver_id: str, user=Depends(require_admin)):
    r = await db.transport_drivers.delete_one({"driver_id": driver_id})
    if r.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Driver not found")
    return {"ok": True}


@router.get("/vehicles")
async def list_vehicles(user=Depends(require_admin)):
    return await db.transport_vehicles.find({}, {"_id": 0}).sort("name", 1).to_list(50)


@router.post("/vehicles")
async def create_vehicle(data: TransportVehicleCreate, user=Depends(require_admin)):
    vehicle = TransportVehicle(**data.model_dump())
    doc = vehicle.model_dump()
    doc["created_at"] = doc["created_at"].isoformat()
    await db.transport_vehicles.insert_one({**doc})
    doc.pop("_id", None)
    return doc


@router.patch("/vehicles/{vehicle_id}")
async def update_vehicle(vehicle_id: str, data: TransportVehicleUpdate, user=Depends(require_admin)):
    patch = {k: v for k, v in data.model_dump().items() if v is not None}
    r = await db.transport_vehicles.update_one({"vehicle_id": vehicle_id}, {"$set": patch})
    if r.matched_count == 0:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    return await db.transport_vehicles.find_one({"vehicle_id": vehicle_id}, {"_id": 0})


@router.delete("/vehicles/{vehicle_id}")
async def delete_vehicle(vehicle_id: str, user=Depends(require_admin)):
    r = await db.transport_vehicles.delete_one({"vehicle_id": vehicle_id})
    if r.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    return {"ok": True}


@router.get("/scheduling-config")
async def get_config(user=Depends(require_admin)):
    return await get_scheduling_config()


@router.put("/scheduling-config")
async def update_config(data: TransportSchedulingConfigUpdate, user=Depends(require_admin)):
    await db.transport_scheduling_config.update_one(
        {"config_id": "transport_scheduling"},
        {"$set": {"buffer_minutes": data.buffer_minutes, "updated_at": now_utc().isoformat()}},
        upsert=True,
    )
    return await get_scheduling_config()
