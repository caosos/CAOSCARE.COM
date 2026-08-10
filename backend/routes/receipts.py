"""Shared operational receipt foundation (Terminal 8).

One generic, append-mostly record for "something meaningful happened" -
task/request lifecycle events, device commands, alert lifecycle, etc. -
so the dashboard, staff, Aria, reporting, and audit systems all read the
same underlying record instead of each domain inventing its own event
log. A receipt POINTS AT a domain object (related_object_type/id); it
does not duplicate that object's own fields.

Other route modules call create_receipt()/update_receipt_status()
directly (Python function calls, not HTTP) when something receipt-worthy
happens - see backend/routes/tasks.py for the first caller. The HTTP
routes below are for reading/querying, plus one admin-only manual-create
escape hatch for anything not yet wired to call create_receipt() itself.
"""
from typing import Optional
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Depends, Query

from deps import db, require_admin
from models import Receipt, ReceiptStatus, TaskSource, now_utc

router = APIRouter(prefix="/receipts", tags=["receipts"])


def _iso(doc: dict) -> dict:
    for k in ("created_at", "acknowledged_at", "completed_at"):
        v = doc.get(k)
        if v and not isinstance(v, str):
            doc[k] = v.isoformat()
    return doc


async def create_receipt(
    *,
    action_type: str,
    related_object_type: str,
    related_object_id: str,
    source: TaskSource = "system",
    resident_id: Optional[str] = None,
    room: Optional[str] = None,
    zone: Optional[str] = None,
    conversation_session_id: Optional[str] = None,
    requested_by: Optional[str] = None,
    assigned_role: Optional[str] = None,
    assigned_user: Optional[str] = None,
    status: ReceiptStatus = "created",
) -> dict:
    """Importable helper - call this directly from other route modules
    when a meaningful action happens. Never blocks the caller's own
    response on anything beyond the insert itself."""
    r = Receipt(
        action_type=action_type,
        related_object_type=related_object_type,
        related_object_id=related_object_id,
        source=source,
        resident_id=resident_id,
        room=room,
        zone=zone,
        conversation_session_id=conversation_session_id,
        requested_by=requested_by,
        assigned_role=assigned_role,
        assigned_user=assigned_user,
        status=status,
    )
    doc = r.model_dump()
    doc["created_at"] = doc["created_at"].isoformat()
    await db.receipts.insert_one(doc)
    doc.pop("_id", None)
    return doc


async def update_receipt_status(
    related_object_type: str,
    related_object_id: str,
    status: ReceiptStatus,
    *,
    result: Optional[str] = None,
    failure_reason: Optional[str] = None,
) -> None:
    """Update the most recent receipt for a domain object - e.g. when a
    task moves from pending to completed. Silently no-ops if no receipt
    exists yet (older objects predate this system)."""
    patch: dict = {"status": status}
    now = now_utc().isoformat()
    if status == "acknowledged":
        patch["acknowledged_at"] = now
    if status in ("completed", "failed", "cancelled"):
        patch["completed_at"] = now
    if result is not None:
        patch["result"] = result
    if failure_reason is not None:
        patch["failure_reason"] = failure_reason
    # update_one() doesn't support sort (only find_one_and_update does) -
    # use that instead to correctly target the most recent receipt if a
    # domain object ever ends up with more than one.
    await db.receipts.find_one_and_update(
        {"related_object_type": related_object_type, "related_object_id": related_object_id},
        {"$set": patch},
        sort=[("created_at", -1)],
    )


@router.get("")
async def list_receipts(
    resident_id: Optional[str] = None,
    related_object_type: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = Query(200, le=1000),
    user=Depends(require_admin),
):
    q: dict = {}
    if resident_id:
        q["resident_id"] = resident_id
    if related_object_type:
        q["related_object_type"] = related_object_type
    if status:
        q["status"] = status
    items = await db.receipts.find(q, {"_id": 0}).sort("created_at", -1).to_list(limit)
    return [_iso(i) for i in items]


@router.get("/{receipt_id}")
async def get_receipt(receipt_id: str, user=Depends(require_admin)):
    doc = await db.receipts.find_one({"receipt_id": receipt_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Receipt not found")
    return _iso(doc)
