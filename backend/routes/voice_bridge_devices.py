"""Admin mapping of voice devices (Voice PE) to room endpoints.

A device id (HA device id, or the satellite entity id) belongs to at most
one room endpoint (Kiosk). Mapping or unmapping writes a receipt with the
before/after mapping. The voice bridge trusts nothing else for identity.
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from deps import db, require_admin
from routes.actor_context import actor_from_user
from routes.receipts import create_receipt

router = APIRouter(prefix="/voice-bridge/devices", tags=["voice-bridge"])


class DeviceMapping(BaseModel):
    kiosk_id: str


async def _owner(device_id: str):
    k = await db.kiosks.find_one({"voice_device_ids": device_id}, {"_id": 0, "kiosk_id": 1, "room": 1})
    return k


async def _receipt(user: dict, action: str, device_id: str, before, after):
    await create_receipt(
        action_type=action, related_object_type="voice_device", related_object_id=device_id,
        status="completed", result=f"{before} -> {after}",
        provenance={**actor_from_user(user).receipt_fields(), "authority": f"admin:{user.get('role')}",
                    "before_state": {"kiosk": before}, "after_state": {"kiosk": after},
                    "result_label": "verified", "next_state": "mapped" if after else "unmapped"})


@router.get("")
async def list_devices(user=Depends(require_admin)):
    kiosks = await db.kiosks.find({"voice_device_ids.0": {"$exists": True}},
                                  {"_id": 0, "kiosk_id": 1, "room": 1, "name": 1, "voice_device_ids": 1}).to_list(500)
    return [{"device_id": d, "kiosk_id": k["kiosk_id"], "room": k.get("room"), "kiosk_name": k.get("name")}
            for k in kiosks for d in k.get("voice_device_ids", [])]


@router.put("/{device_id}")
async def map_device(device_id: str, body: DeviceMapping, user=Depends(require_admin)):
    device_id = device_id.strip()
    if not device_id:
        raise HTTPException(422, "device_id is required")
    target = await db.kiosks.find_one({"kiosk_id": body.kiosk_id}, {"_id": 0, "kiosk_id": 1, "room": 1})
    if not target or not target.get("room"):
        raise HTTPException(404, "room endpoint not found")
    before = await _owner(device_id)
    await db.kiosks.update_many({"voice_device_ids": device_id, "kiosk_id": {"$ne": body.kiosk_id}},
                                {"$pull": {"voice_device_ids": device_id}})
    await db.kiosks.update_one({"kiosk_id": body.kiosk_id}, {"$addToSet": {"voice_device_ids": device_id}})
    await _receipt(user, "voice_device_mapped", device_id, (before or {}).get("kiosk_id"), body.kiosk_id)
    return {"device_id": device_id, "kiosk_id": body.kiosk_id, "room": target["room"],
            "previous_kiosk_id": (before or {}).get("kiosk_id")}


@router.delete("/{device_id}")
async def unmap_device(device_id: str, user=Depends(require_admin)):
    before = await _owner(device_id)
    if not before:
        raise HTTPException(404, "device is not mapped")
    await db.kiosks.update_many({"voice_device_ids": device_id}, {"$pull": {"voice_device_ids": device_id}})
    await _receipt(user, "voice_device_unmapped", device_id, before["kiosk_id"], None)
    return {"device_id": device_id, "previous_kiosk_id": before["kiosk_id"]}
