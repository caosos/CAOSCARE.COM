"""Phone extensions on the local Asterisk and what they mean to CAOSCare
(room handset / front desk / Aria). Admin-managed; the Asterisk side is
configured to match (telephony/asterisk/)."""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

from deps import db, require_admin
from models_calls import PhoneEndpoint, PhoneEndpointCreate

router = APIRouter(prefix="/telephony/endpoints", tags=["telephony"])


async def endpoint_for_extension(extension: Optional[str]) -> Optional[dict]:
    if not extension:
        return None
    return await db.phone_endpoints.find_one({"extension": extension, "active": True}, {"_id": 0})


async def front_desk_extension() -> Optional[str]:
    ep = await db.phone_endpoints.find_one({"kind": "front_desk", "active": True}, {"_id": 0},
                                           sort=[("created_at", 1)])
    return ep["extension"] if ep else None


async def resident_for_room(room: Optional[str]) -> Optional[dict]:
    if not room:
        return None
    return await db.residents.find_one({"room": room}, {"_id": 0, "resident_id": 1, "name": 1,
                                                       "preferred_name": 1, "room": 1})


@router.get("")
async def list_endpoints(user=Depends(require_admin)):
    return await db.phone_endpoints.find({"active": True}, {"_id": 0}).sort("extension", 1).to_list(200)


@router.post("")
async def add_endpoint(body: PhoneEndpointCreate, user=Depends(require_admin)):
    if body.kind == "room" and not body.room:
        raise HTTPException(status_code=400, detail="A room handset needs its room")
    if await endpoint_for_extension(body.extension):
        raise HTTPException(status_code=409, detail="Extension already in use")
    doc = PhoneEndpoint(**body.model_dump()).model_dump()
    doc["created_at"] = doc["created_at"].isoformat()
    await db.phone_endpoints.insert_one(dict(doc))
    doc.pop("_id", None)
    return doc


@router.delete("/{endpoint_id}")
async def retire_endpoint(endpoint_id: str, user=Depends(require_admin)):
    res = await db.phone_endpoints.update_one({"endpoint_id": endpoint_id}, {"$set": {"active": False}})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Extension not found")
    return {"ok": True}
