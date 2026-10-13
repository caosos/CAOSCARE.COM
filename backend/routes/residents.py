"""Residents CRUD."""
from fastapi import APIRouter, HTTPException, Depends
from typing import List
from models import Resident, ResidentCreate
from deps import db, get_current_user
from routes.receipts import create_receipt
from routes.kiosk_identity import resident_for_kiosk
from aria_guidance_profiles import normalize_guidance_profile, DEFAULT as DEFAULT_GUIDANCE_PROFILE

router = APIRouter(prefix="/residents", tags=["residents"])

LIVING_COMMUNITY_SCOPE = "living_community"
LIVING_COMMUNITY_ID = "sim:community:living-80-v1"
_MANAGED_DETAIL = "This resident is managed by the living-community simulator"


def _refuse_managed_resident(doc: dict) -> None:
    """Keep generic CRUD outside the simulator's resident write boundary."""
    if doc.get("simulation_scope") != LIVING_COMMUNITY_SCOPE:
        return
    if doc.get("simulation_community_id") != LIVING_COMMUNITY_ID:
        raise HTTPException(
            status_code=409,
            detail="Living-community resident markers are invalid; no change was made",
        )
    if doc.get("synthetic") is True:
        raise HTTPException(status_code=409, detail=f"{_MANAGED_DETAIL}; no change was made")


def _generic_mutation_filter(resident_id: str) -> dict:
    """Atomic inverse of the pre-read refusal, closing marker-change races."""
    return {
        "resident_id": resident_id,
        "$or": [
            {"simulation_scope": {"$ne": LIVING_COMMUNITY_SCOPE}},
            {
                "simulation_scope": LIVING_COMMUNITY_SCOPE,
                "simulation_community_id": LIVING_COMMUNITY_ID,
                "synthetic": {"$ne": True},
            },
        ],
    }


async def _mutation_miss(resident_id: str) -> None:
    """Report a concurrent delete separately from a newly protected row."""
    current = await db.residents.find_one({"resident_id": resident_id}, {"_id": 0})
    if not current:
        raise HTTPException(status_code=404, detail="Resident not found")
    _refuse_managed_resident(current)
    raise HTTPException(status_code=409, detail="Resident changed during the request; retry")


def _serialize(doc: dict) -> dict:
    if isinstance(doc.get("created_at"), str):
        return {**doc, "aria_guidance_profile": normalize_guidance_profile(doc.get("aria_guidance_profile"))}
    doc = {**doc}
    ca = doc.get("created_at")
    if hasattr(ca, "isoformat"):
        doc["created_at"] = ca.isoformat()
    doc["aria_guidance_profile"] = normalize_guidance_profile(doc.get("aria_guidance_profile"))
    return doc


@router.get("")
async def list_residents(user=Depends(get_current_user)):
    items = await db.residents.find({}, {"_id": 0}).sort("name", 1).to_list(1000)
    return [_serialize(item) for item in items]


@router.post("")
async def create_resident(data: ResidentCreate, user=Depends(get_current_user)):
    if data.aria_guidance_profile != DEFAULT_GUIDANCE_PROFILE and user.get("role") not in ("owner", "admin"):
        raise HTTPException(status_code=403, detail="Only an owner or admin can select a non-default Aria conversation style")
    resident = Resident(**data.model_dump())
    doc = resident.model_dump()
    doc["created_at"] = doc["created_at"].isoformat()
    await db.residents.insert_one(doc)
    doc.pop("_id", None)
    if data.aria_guidance_profile != DEFAULT_GUIDANCE_PROFILE:
        await _record_guidance_change(doc, user, None, data.aria_guidance_profile)
    return _serialize(doc)


@router.get("/{resident_id}")
async def get_resident(resident_id: str, user=Depends(get_current_user)):
    doc = await db.residents.find_one({"resident_id": resident_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Resident not found")
    return _serialize(doc)


@router.put("/{resident_id}")
async def update_resident(resident_id: str, data: ResidentCreate, user=Depends(get_current_user)):
    before = await db.residents.find_one({"resident_id": resident_id}, {"_id": 0})
    if not before:
        raise HTTPException(status_code=404, detail="Resident not found")
    _refuse_managed_resident(before)
    old_profile = normalize_guidance_profile(before.get("aria_guidance_profile"))
    new_profile = normalize_guidance_profile(data.aria_guidance_profile)
    if old_profile != new_profile and user.get("role") not in ("owner", "admin"):
        raise HTTPException(status_code=403, detail="Only an owner or admin can change Aria's conversation style")
    upd = data.model_dump()
    r = await db.residents.update_one(_generic_mutation_filter(resident_id), {"$set": upd})
    if r.matched_count == 0:
        await _mutation_miss(resident_id)
    doc = await db.residents.find_one({"resident_id": resident_id}, {"_id": 0})
    if old_profile != new_profile:
        await _record_guidance_change(doc, user, old_profile, new_profile)
    return _serialize(doc)


async def _record_guidance_change(resident: dict, user: dict, before: str | None, after: str) -> None:
    await create_receipt(
        action_type="resident_aria_guidance_profile_updated",
        related_object_type="resident", related_object_id=resident["resident_id"],
        source="staff", resident_id=resident["resident_id"], room=resident.get("room"),
        requested_by=user.get("user_id"), status="completed", result=f"{before or 'new'} -> {after}",
        provenance={"actor_id": user.get("user_id"), "actor_name": user.get("name"),
                    "actor_role": user.get("role"), "actor_type": "real-human",
                    "identity_basis": "authenticated", "authority": f"admin_override:{user.get('role')}",
                    "before_state": {"aria_guidance_profile": before},
                    "after_state": {"aria_guidance_profile": after}, "result_label": "verified"},
    )


@router.delete("/{resident_id}")
async def delete_resident(resident_id: str, user=Depends(get_current_user)):
    before = await db.residents.find_one({"resident_id": resident_id}, {"_id": 0})
    if not before:
        raise HTTPException(status_code=404, detail="Resident not found")
    _refuse_managed_resident(before)
    r = await db.residents.delete_one(_generic_mutation_filter(resident_id))
    if r.deleted_count == 0:
        await _mutation_miss(resident_id)
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
    existing = await db.residents.find_one({"resident_id": resident_id}, {"_id": 0})
    if not existing:
        raise HTTPException(status_code=404, detail="Resident not found")
    _refuse_managed_resident(existing)
    old_name = existing.get("preferred_name") or ""
    result = await db.residents.update_one(
        _generic_mutation_filter(resident_id),
        {"$set": {"preferred_name": name}},
    )
    if result.matched_count == 0:
        await _mutation_miss(resident_id)
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


# Unauthenticated: only what the room screen displays or sends back. Never
# medical notes, contacts, DOB, preferences, memory or thresholds (B3).
PUBLIC_KIOSK_RESIDENT_FIELDS = ("resident_id", "name", "preferred_name", "room")


@router.get("/public/by-kiosk/{kiosk_id}")
async def resident_by_kiosk(kiosk_id: str):
    """Public endpoint used by kiosks to look up the resident tied to their room."""
    kiosk = await db.kiosks.find_one({"kiosk_id": kiosk_id}, {"_id": 0})
    if not kiosk:
        raise HTTPException(status_code=404, detail="Kiosk not found")
    resident = await resident_for_kiosk(kiosk, {f: 1 for f in PUBLIC_KIOSK_RESIDENT_FIELDS})
    return {"kiosk": kiosk, "resident": resident}


# Movement/stats/briefing (aggregation & reporting over resident data) live
# in resident_analytics.py, mounted alongside this router under the same
# /residents prefix — see backend/routes/resident_analytics.py.
