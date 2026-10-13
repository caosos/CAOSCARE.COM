"""Kiosks + Zones CRUD."""
import re
from datetime import timedelta
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel, Field
from models import Kiosk, KioskCreate, KioskUpdate, Zone, ZoneCreate, now_utc
from deps import db, get_current_user, require_admin
from routes.receipts import create_receipt
from routes.session_grounding import find_live_session

# What a caller who is not an admin/owner may see of each kiosk (RQ-035,
# packet P2): enough to identify a room, nothing else.
PUBLIC_KIOSK_FIELDS = ("kiosk_id", "room")

router = APIRouter(tags=["kiosks"])


class VoiceTvAudioDuckChange(BaseModel):
    resident_id: str = Field(min_length=1, max_length=100)
    session_id: str = Field(min_length=1, max_length=100)
    enabled: bool
    confirmed: bool = False
    confirmation_text: Optional[str] = Field(default=None, max_length=200)
    request_text: Optional[str] = Field(default=None, max_length=500)


_AFFIRMATIVE = re.compile(
    r"^\s*(yes|yeah|yep|correct|that(?:'s| is) right|please do|yes\s*,?\s*that(?:'s| is) right)[.!]?\s*$",
    re.I,
)


# Kiosks ---------------------------------
async def all_kiosks():
    """Full kiosk rows, no access check - for in-process callers only
    (Admin Aria's executor). HTTP callers go through list_kiosks."""
    return await db.kiosks.find({}, {"_id": 0}).sort("room", 1).to_list(1000)


@router.get("/kiosks")
async def list_kiosks(request: Request):
    """Owner/admin (bearer token or session): full rows. Anyone else,
    including no sign-in: only kiosk_id + room. Room screens do not use this
    list (they use /kiosks/public-demo or their own id in the URL)."""
    items = await all_kiosks()
    try:
        user = await get_current_user(request)
    except HTTPException:
        user = None
    if user and user.get("role") in ("owner", "admin"):
        return items
    return [{f: k.get(f) for f in PUBLIC_KIOSK_FIELDS} for k in items]


@router.get("/kiosks/public-demo")
async def public_demo_kiosk():
    """Public — the ONLY thing the logged-out /kiosk/demo route may resolve
    to (see frontend/src/pages/Kiosk.jsx). Previously that route fetched
    every kiosk and took whatever GET /kiosks happened to sort first -
    database order, not a deliberate choice, which is how a real test
    kiosk ended up as the public face of the product. Returns 404 with a
    specific, checkable detail when nothing is configured - never a silent
    fallback to an arbitrary kiosk."""
    kiosk = await db.kiosks.find_one({"public_demo": True}, {"_id": 0})
    if not kiosk:
        raise HTTPException(status_code=404, detail="No public demo kiosk is configured. An admin must designate one in Kiosks.")
    return kiosk


@router.get("/kiosks/{kiosk_id}/active-emergency")
async def active_emergency_for_kiosk(kiosk_id: str):
    """Public — polled by the Kiosk UI every few seconds.

    Returns the most-recent unresolved emergency alert with auto_voice=True that
    belongs to this kiosk's zone / room. If the kiosk is flagged is_central it
    listens for ANY facility-wide emergency.
    """
    kiosk = await db.kiosks.find_one({"kiosk_id": kiosk_id}, {"_id": 0})
    if not kiosk:
        raise HTTPException(status_code=404, detail="Kiosk not found")

    q = {
        "auto_voice": True,
        # `status` is deliberately untouched by session lifecycle (see
        # Alert.activation_consumed_at in models.py) - "active" alone
        # would keep resurfacing an alert whose own session already ran
        # and ended (2026-08-30 defect, room 401), so activation state is
        # checked separately. A 2026-09-06 fixed 5-minute created_at
        # cutoff used to also gate this - removed, because a real Level 1
        # resident event can legitimately stay open far longer than 5
        # minutes and a later repeat press must still be able to
        # reactivate Aria (routes/resident_activation.py resets
        # activation_consumed_at to None on every coalesced press,
        # regardless of the event's age).
        "status": {"$in": ["active", "acknowledged"]},
        "activation_consumed_at": None,
    }
    pinned = kiosk.get("resident_id")
    if pinned:
        # A pinned kiosk speaks for one resident only (RQ-037): another
        # resident's event in the same room (e.g. the room's own pendant)
        # must not start a session under the pinned identity.
        q["resident_id"] = pinned
    if not kiosk.get("is_central"):
        # A room endpoint must never activate another room's resident.
        # Null/empty zones are not routing identities. Zone-only kiosks
        # retain their explicitly configured zone scope.
        if kiosk.get("room"):
            q["room"] = kiosk["room"]
        elif kiosk.get("zone"):
            q["zone"] = kiosk["zone"]
        else:
            return {"kiosk_is_central": False, "alert": None}

    alert = await db.alerts.find_one(q, {"_id": 0}, sort=[("created_at", -1)])
    return {"kiosk_is_central": bool(kiosk.get("is_central")), "alert": alert}


async def _check_pin(resident_id):
    """A pin must name a real resident (RQ-037)."""
    if resident_id and not await db.residents.find_one({"resident_id": resident_id}, {"_id": 1}):
        raise HTTPException(status_code=404, detail="Pinned resident not found")


@router.post("/kiosks")
async def create_kiosk(data: KioskCreate, user=Depends(require_admin)):
    await _check_pin(data.resident_id)
    k = Kiosk(**data.model_dump())
    doc = k.model_dump()
    doc["created_at"] = doc["created_at"].isoformat()
    authorization = await create_receipt(
        action_type="kiosk_create_authorized", related_object_type="kiosk",
        related_object_id=doc["kiosk_id"], source="staff", resident_id=doc.get("resident_id"),
        room=doc.get("room"), zone=doc.get("zone"), requested_by=user.get("user_id"), status="created",
        result="authenticated admin kiosk creation authorized",
        provenance={"actor_id": user.get("user_id"), "actor_type": "real-human",
                    "actor_name": user.get("name"), "actor_role": user.get("role"),
                    "identity_basis": "authenticated", "authority": f"admin_override:{user.get('role')}",
                    "before_state": None, "after_state": doc, "result_label": "verified"},
    )
    await db.kiosks.insert_one(doc)
    doc.pop("_id", None)
    await create_receipt(
        action_type="kiosk_created", related_object_type="kiosk", related_object_id=doc["kiosk_id"],
        source="staff", resident_id=doc.get("resident_id"), room=doc.get("room"), zone=doc.get("zone"),
        requested_by=user.get("user_id"), status="completed", result="kiosk created",
        provenance={"actor_id": user.get("user_id"), "actor_type": "real-human",
                    "actor_name": user.get("name"), "actor_role": user.get("role"),
                    "identity_basis": "authenticated", "authority": f"admin_override:{user.get('role')}",
                    "parent_receipt_id": authorization["receipt_id"], "before_state": None,
                    "after_state": doc, "result_label": "verified"},
    )
    return doc


@router.put("/kiosks/{kiosk_id}")
async def update_kiosk(kiosk_id: str, data: KioskCreate, user=Depends(require_admin)):
    await _check_pin(data.resident_id)
    existing = await db.kiosks.find_one({"kiosk_id": kiosk_id}, {"_id": 0})
    if not existing:
        raise HTTPException(status_code=404, detail="Kiosk not found")
    authorization = await create_receipt(
        action_type="kiosk_settings_change_authorized", related_object_type="kiosk",
        related_object_id=kiosk_id, source="staff", resident_id=existing.get("resident_id"),
        room=existing.get("room"), zone=existing.get("zone"), requested_by=user.get("user_id"),
        status="created", result="authenticated admin full kiosk update authorized",
        provenance={"actor_id": user.get("user_id"), "actor_type": "real-human",
                    "actor_name": user.get("name"), "actor_role": user.get("role"),
                    "identity_basis": "authenticated", "authority": f"admin_override:{user.get('role')}",
                    "before_state": existing, "after_state": data.model_dump(), "result_label": "verified"},
    )
    r = await db.kiosks.update_one({"kiosk_id": kiosk_id}, {"$set": data.model_dump()})
    if r.matched_count == 0:
        raise HTTPException(status_code=404, detail="Kiosk not found")
    doc = await db.kiosks.find_one({"kiosk_id": kiosk_id}, {"_id": 0})
    await create_receipt(
        action_type="kiosk_settings_updated", related_object_type="kiosk", related_object_id=kiosk_id,
        source="staff", resident_id=doc.get("resident_id"), room=doc.get("room"), zone=doc.get("zone"),
        requested_by=user.get("user_id"), status="completed", result="full kiosk settings updated",
        provenance={"actor_id": user.get("user_id"), "actor_type": "real-human",
                    "actor_name": user.get("name"), "actor_role": user.get("role"),
                    "identity_basis": "authenticated", "authority": f"admin_override:{user.get('role')}",
                    "parent_receipt_id": authorization["receipt_id"], "before_state": existing,
                    "after_state": doc, "result_label": "verified"},
    )
    return doc


@router.patch("/kiosks/{kiosk_id}")
async def patch_kiosk(kiosk_id: str, data: KioskUpdate, user=Depends(require_admin)):
    """Partial update - added for the public-demo toggle (a per-row admin
    action, not a full re-submit of every field). Enforces at most one
    public_demo kiosk: setting it true on this kiosk clears it on every
    other one in the same operation, so there is never a moment with two
    (or, after a failed partial update, zero-then-two) demo kiosks."""
    updates = data.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")
    existing = await db.kiosks.find_one({"kiosk_id": kiosk_id}, {"_id": 0})
    if not existing:
        raise HTTPException(status_code=404, detail="Kiosk not found")
    if "resident_id" in updates:
        updates["resident_id"] = updates["resident_id"] or None
        await _check_pin(updates["resident_id"])
    authorization = await create_receipt(
        action_type="kiosk_settings_change_authorized", related_object_type="kiosk",
        related_object_id=kiosk_id, source="staff", resident_id=existing.get("resident_id"),
        room=existing.get("room"), zone=existing.get("zone"), requested_by=user.get("user_id"),
        status="created", result="authenticated admin settings change authorized",
        provenance={"actor_id": user.get("user_id"), "actor_type": "real-human",
                    "actor_name": user.get("name"), "actor_role": user.get("role"),
                    "identity_basis": "authenticated", "authority": f"admin_override:{user.get('role')}",
                    "before_state": {k: existing.get(k) for k in updates},
                    "after_state": updates, "result_label": "verified"},
    )
    if updates.get("public_demo") is True:
        await db.kiosks.update_many({"kiosk_id": {"$ne": kiosk_id}}, {"$set": {"public_demo": False}})
    await db.kiosks.update_one({"kiosk_id": kiosk_id}, {"$set": updates})
    updated = await db.kiosks.find_one({"kiosk_id": kiosk_id}, {"_id": 0})
    await create_receipt(
        action_type="kiosk_settings_updated", related_object_type="kiosk", related_object_id=kiosk_id,
        source="staff", resident_id=updated.get("resident_id"), room=updated.get("room"),
        zone=updated.get("zone"), requested_by=user.get("user_id"), status="completed",
        result="kiosk settings updated",
        provenance={"actor_id": user.get("user_id"), "actor_type": "real-human",
                    "actor_name": user.get("name"), "actor_role": user.get("role"),
                    "identity_basis": "authenticated", "authority": f"admin_override:{user.get('role')}",
                    "parent_receipt_id": authorization["receipt_id"],
                    "before_state": {k: existing.get(k) for k in updates},
                    "after_state": {k: updated.get(k) for k in updates}, "result_label": "verified"},
    )
    return updated


@router.post("/kiosks/{kiosk_id}/tv-audio-duck/voice")
async def voice_tv_audio_duck(kiosk_id: str, data: VoiceTvAudioDuckChange):
    """Confirmation-gated Resident Aria write for the room preference."""
    kiosk = await db.kiosks.find_one({"kiosk_id": kiosk_id}, {"_id": 0})
    if not kiosk:
        raise HTTPException(status_code=404, detail="Kiosk not found")
    live = await find_live_session(data.resident_id, data.session_id)
    if not live or live.get("room") != kiosk.get("room") or live.get("kiosk_id") != kiosk_id:
        raise HTTPException(status_code=403, detail="No live Aria session for this exact kiosk")

    key = {"session_id": data.session_id, "kiosk_id": kiosk_id, "setting": "tv_audio_duck"}
    now = now_utc()
    if not data.confirmed:
        await db.kiosk_preference_confirmations.update_one(key, {"$set": {
            **key, "resident_id": data.resident_id, "enabled": data.enabled,
            "request_text": (data.request_text or "").strip(),
            "requested_at": now.isoformat(), "expires_at": (now + timedelta(minutes=5)).isoformat(),
        }}, upsert=True)
        wording = (
            "To confirm, when I wake up, you want me to lower the TV volume while we talk, "
            "then restore it when we finish. Is that right?"
            if data.enabled else
            "To confirm, when I wake up, you don't want me to lower the TV volume; you want it "
            "to stay the same. That can make it harder for us to hear each other. Is that right?"
        )
        return {"ok": False, "awaiting_confirmation": True, "message": wording}

    pending = await db.kiosk_preference_confirmations.find_one({
        **key, "resident_id": data.resident_id, "enabled": data.enabled,
        "expires_at": {"$gte": now.isoformat()},
    }, {"_id": 0})
    heard = (data.confirmation_text or "").strip()
    if not pending or not _AFFIRMATIVE.search(heard):
        return {"ok": False, "awaiting_confirmation": bool(pending),
                "message": "I haven't changed it. Please say yes if that setting is what you want."}

    before = kiosk.get("tv_audio_duck", True)
    authorization = await create_receipt(
        action_type="kiosk_tv_audio_duck_change_authorized", related_object_type="kiosk",
        related_object_id=kiosk_id, source="aria_voice", resident_id=data.resident_id,
        room=kiosk.get("room"), zone=kiosk.get("zone"), conversation_session_id=data.session_id,
        requested_by=data.resident_id, status="created", result="confirmed preference change authorized",
        provenance={"actor_id": data.resident_id, "actor_type": "real-human", "actor_role": "resident",
                    "channel": "resident_aria_voice", "identity_basis": "live_exact_kiosk_session",
                    "authority": "resident_room_preference:confirmed_voice",
                    "request_text": pending.get("request_text") or None,
                    "confirmation_text": heard,
                    "before_state": {"tv_audio_duck": before},
                    "after_state": {"tv_audio_duck": data.enabled}, "result_label": "verified"},
    )
    await db.kiosks.update_one({"kiosk_id": kiosk_id}, {"$set": {"tv_audio_duck": data.enabled}})
    await db.kiosk_preference_confirmations.delete_one(key)
    await create_receipt(
        action_type="kiosk_tv_audio_duck_updated", related_object_type="kiosk", related_object_id=kiosk_id,
        source="aria_voice", resident_id=data.resident_id, room=kiosk.get("room"), zone=kiosk.get("zone"),
        conversation_session_id=data.session_id, requested_by=data.resident_id, status="completed",
        result=f"tv_audio_duck {before} -> {data.enabled}",
        provenance={"actor_id": data.resident_id, "actor_type": "real-human", "actor_role": "resident",
                    "channel": "resident_aria_voice", "identity_basis": "live_exact_kiosk_session",
                    "authority": "resident_room_preference:confirmed_voice",
                    "parent_receipt_id": authorization["receipt_id"],
                    "request_text": pending.get("request_text") or None,
                    "confirmation_text": heard,
                    "before_state": {"tv_audio_duck": before},
                    "after_state": {"tv_audio_duck": data.enabled}, "result_label": "verified"},
    )
    state = "on" if data.enabled else "off"
    return {"ok": True, "enabled": data.enabled,
            "message": f"Okay. Automatic TV volume lowering is {state} for this room."}


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
