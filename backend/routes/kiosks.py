"""Kiosks + Zones CRUD."""
from fastapi import APIRouter, HTTPException, Depends
from models import Kiosk, KioskCreate, KioskUpdate, Zone, ZoneCreate
from deps import db, get_current_user

router = APIRouter(tags=["kiosks"])


# Kiosks ---------------------------------
@router.get("/kiosks")
async def list_kiosks():
    """Public list - kiosks need to self-identify without auth."""
    items = await db.kiosks.find({}, {"_id": 0}).sort("room", 1).to_list(1000)
    return items


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
    if not kiosk.get("is_central"):
        # Same zone OR same room
        q["$or"] = [{"zone": kiosk.get("zone")}, {"room": kiosk.get("room")}]

    alert = await db.alerts.find_one(q, {"_id": 0}, sort=[("created_at", -1)])
    return {"kiosk_is_central": bool(kiosk.get("is_central")), "alert": alert}


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


@router.patch("/kiosks/{kiosk_id}")
async def patch_kiosk(kiosk_id: str, data: KioskUpdate, user=Depends(get_current_user)):
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
    if updates.get("public_demo") is True:
        await db.kiosks.update_many({"kiosk_id": {"$ne": kiosk_id}}, {"$set": {"public_demo": False}})
    await db.kiosks.update_one({"kiosk_id": kiosk_id}, {"$set": updates})
    return await db.kiosks.find_one({"kiosk_id": kiosk_id}, {"_id": 0})


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
