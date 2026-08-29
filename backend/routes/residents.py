"""Residents CRUD."""
from fastapi import APIRouter, HTTPException, Depends
from typing import List
from models import Resident, ResidentCreate
from deps import db, get_current_user
from routes.receipts import create_receipt

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


@router.patch("/{resident_id}/preferred-name")
async def update_preferred_name(resident_id: str, body: dict):
    """Public endpoint — the Realtime AI tool dispatcher PATCHes this when the
    resident corrects their name mid-call ('it's Margaret, not Maggie'). No
    auth because we're inside an active voice session, not an admin flow.
    Validates the name shape so the model can't blow away the field with empty
    strings or 100-character payloads.

    TSB-001: this mutation previously left zero audit trail (old value, who/
    what session triggered it) — a wrong name could land silently with
    nothing to catch it. Now writes a receipt with the old->new value and,
    when the caller supplies them, the room/conversation session it came
    from."""
    body = body or {}
    name = (body.get("preferred_name") or "").strip()
    if not name or len(name) > 60:
        raise HTTPException(status_code=400, detail="preferred_name must be 1-60 chars")
    existing = await db.residents.find_one({"resident_id": resident_id}, {"_id": 0, "preferred_name": 1})
    if not existing:
        raise HTTPException(status_code=404, detail="Resident not found")
    old_name = existing.get("preferred_name") or ""
    await db.residents.update_one(
        {"resident_id": resident_id},
        {"$set": {"preferred_name": name}},
    )
    await create_receipt(
        action_type="preferred_name.update",
        related_object_type="resident",
        related_object_id=resident_id,
        source="aria_voice",
        resident_id=resident_id,
        room=body.get("room"),
        conversation_session_id=body.get("session_id"),
        status="completed",
        result=f"{old_name!r} -> {name!r}",
    )
    return {"ok": True, "preferred_name": name}


@router.get("/public/by-kiosk/{kiosk_id}")
async def resident_by_kiosk(kiosk_id: str):
    """Public endpoint used by kiosks to look up the resident tied to their room."""
    kiosk = await db.kiosks.find_one({"kiosk_id": kiosk_id}, {"_id": 0})
    if not kiosk:
        raise HTTPException(status_code=404, detail="Kiosk not found")
    resident = await db.residents.find_one({"room": kiosk["room"]}, {"_id": 0})
    return {"kiosk": kiosk, "resident": resident}


# Movement/stats/briefing (aggregation & reporting over resident data) live
# in resident_analytics.py, mounted alongside this router under the same
# /residents prefix — see backend/routes/resident_analytics.py.
