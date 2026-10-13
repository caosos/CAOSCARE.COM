"""Receipts for device REGISTRY changes (create / update / delete a room device record).
A device record decides what a room's commands reach - e.g. switching a TV from a simulator to
a real IR blaster - so it is a meaningful state change: no change without a receipt, no receipt
without provenance (actor, authority, before, after). Owner/admin only, like device commands."""
from fastapi import HTTPException

from routes.receipts import create_receipt

_FIELDS = ("label", "kind", "protocol", "room", "resident_id", "endpoint", "ir_codeset", "capabilities", "inputs",
           "vendor", "model", "online", "notes")


def require_device_admin(user: dict) -> None:
    if user.get("role") not in ("owner", "admin"):
        raise HTTPException(status_code=403, detail="Only an owner or admin can change room devices")


def _summary(doc):
    return {k: doc.get(k) for k in _FIELDS if doc and k in doc} if doc else None


async def record_device_change(change: str, device_id: str, actor: dict, before=None, after=None, note=None) -> dict:
    """change: created | updated | deleted. actor: user_id/name/role plus optional actor_type/identity_basis."""
    doc = after or before or {}
    return await create_receipt(
        action_type=f"device_record_{change}", related_object_type="device", related_object_id=device_id,
        source="staff", resident_id=doc.get("resident_id"), room=doc.get("room"), requested_by=actor.get("user_id"),
        status="completed", result=note or f"device record {change}",
        provenance={"actor_id": actor.get("user_id"), "actor_name": actor.get("name"), "actor_role": actor.get("role"),
                    "actor_type": actor.get("actor_type", "real-human"),
                    "identity_basis": actor.get("identity_basis", "authenticated"),
                    "authority": f"admin_override:{actor.get('role')}",
                    "before_state": _summary(before), "after_state": _summary(after),
                    "result_label": "verified"})   # read back from the store right after the write
