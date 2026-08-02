"""Aria capability portfolio — Terminal 5A.

Durable registry of every device/service/workflow/tool Aria may control.
Aria may only claim to control a capability when its status is
`verified_control` and the requested action is in `supported_actions` —
this backend is the source of truth for that check, not the model's
own claims.

Each verification attempt (`POST /capabilities/{id}/verify`) writes an
immutable receipt to db.aria_capability_receipts and updates the
capability's status/verification_state/last_verified_at, mirroring the
Hardware Receipt pattern in routes/hardware.py.
"""
from fastapi import APIRouter, HTTPException, Depends

from deps import db, require_owner
from models import (
    AriaCapability, AriaCapabilityCreate, AriaCapabilityUpdate,
    AriaCapabilityVerify, now_utc, uid,
)

router = APIRouter(prefix="/capabilities", tags=["capabilities"])


def _iso(doc: dict) -> dict:
    for k in ("created_at", "updated_at", "last_verified_at", "tested_at"):
        v = doc.get(k)
        if v and not isinstance(v, str):
            doc[k] = v.isoformat()
    return doc


@router.get("")
async def list_capabilities(user=Depends(require_owner)):
    items = await db.aria_capabilities.find({}, {"_id": 0}).sort("created_at", 1).to_list(500)
    return [_iso(i) for i in items]


@router.get("/{capability_id}")
async def get_capability(capability_id: str, user=Depends(require_owner)):
    doc = await db.aria_capabilities.find_one({"capability_id": capability_id}, {"_id": 0})
    if not doc:
        raise HTTPException(404, detail="Capability not found")
    return _iso(doc)


@router.post("")
async def create_capability(payload: AriaCapabilityCreate, user=Depends(require_owner)):
    cap = AriaCapability(**payload.model_dump())
    doc = cap.model_dump()
    doc["created_at"] = doc["created_at"].isoformat()
    doc["updated_at"] = doc["updated_at"].isoformat()
    await db.aria_capabilities.insert_one(doc)
    doc.pop("_id", None)
    return _iso(doc)


@router.patch("/{capability_id}")
async def update_capability(capability_id: str, payload: AriaCapabilityUpdate, user=Depends(require_owner)):
    existing = await db.aria_capabilities.find_one({"capability_id": capability_id}, {"_id": 0})
    if not existing:
        raise HTTPException(404, detail="Capability not found")
    updates = {k: v for k, v in payload.model_dump().items() if v is not None}
    if not updates:
        return _iso(existing)
    updates["updated_at"] = now_utc().isoformat()
    await db.aria_capabilities.update_one({"capability_id": capability_id}, {"$set": updates})
    doc = await db.aria_capabilities.find_one({"capability_id": capability_id}, {"_id": 0})
    return _iso(doc)


@router.post("/{capability_id}/verify")
async def verify_capability(capability_id: str, payload: AriaCapabilityVerify, user=Depends(require_owner)):
    """Records a verification attempt. This is the receipt — success or
    failure both get logged so a capability's history is never lost."""
    existing = await db.aria_capabilities.find_one({"capability_id": capability_id}, {"_id": 0})
    if not existing:
        raise HTTPException(404, detail="Capability not found")

    tested_at = now_utc()
    receipt = {
        "receipt_id": uid("capr"),
        "capability_id": capability_id,
        "outcome": payload.outcome,
        "note": payload.note,
        "tested_at": tested_at.isoformat(),
        "tested_by": user.get("user_id") if isinstance(user, dict) else None,
    }
    await db.aria_capability_receipts.insert_one(dict(receipt))
    receipt.pop("_id", None)

    updates = {
        "status": payload.outcome,
        "verification_state": payload.note or f"{payload.outcome} at {tested_at.isoformat()}",
        "last_verified_at": tested_at.isoformat(),
        "updated_at": tested_at.isoformat(),
    }
    await db.aria_capabilities.update_one({"capability_id": capability_id}, {"$set": updates})
    doc = await db.aria_capabilities.find_one({"capability_id": capability_id}, {"_id": 0})
    return {"capability": _iso(doc), "receipt": receipt}


@router.get("/{capability_id}/receipts")
async def list_receipts(capability_id: str, user=Depends(require_owner)):
    items = await db.aria_capability_receipts.find(
        {"capability_id": capability_id}, {"_id": 0},
    ).sort("tested_at", -1).to_list(200)
    return items


async def get_capability_summary() -> str:
    """Concise text summary of the portfolio for the start of every Aria
    voice session (Terminal 5A "Voice integration rule"). Not yet wired
    into routes/realtime.py — that happens once the voice foundation
    (Phase C/D) is unblocked and tool routing is connected to this registry."""
    items = await db.aria_capabilities.find({}, {"_id": 0}).sort("created_at", 1).to_list(500)
    if not items:
        return "No capabilities registered yet."
    lines = []
    for i in items:
        blocker = f" (blocked: {i['current_blocker']})" if i.get("current_blocker") else ""
        lines.append(f"- {i['name']} [{i['status']}]{blocker}")
    return "Aria capability portfolio:\n" + "\n".join(lines)
