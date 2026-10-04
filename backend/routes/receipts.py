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
import time
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends, Query

from deps import db, require_admin
from models import Receipt, ReceiptStatus, TaskSource, now_utc
from routes.capacity_telemetry import RECORDER

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
    result: Optional[str] = None,
    failure_reason: Optional[str] = None,
    provenance: Optional[dict] = None,
    receipt_id: Optional[str] = None,
) -> dict:
    """Importable helper - call this directly from other route modules
    when a meaningful action happens. Never blocks the caller's own
    response on anything beyond the insert itself.

    `result` is for actions that complete synchronously in the same call
    (no separate pending phase) - e.g. an instant field update - so the
    caller isn't forced through a created->update_receipt_status("completed")
    round trip, and isn't tempted to reach for update_receipt_status's
    "most recent receipt for this object" lookup when a more specific one
    already exists.

    `provenance` carries the SIM-0 fields (actor, authority, parent /
    correlation receipt, before/after state, result label, provider refs,
    next state) built by task_lifecycle.py; `receipt_id` lets that caller
    reference the receipt from the task's history before it is written."""
    extra = dict(provenance or {})
    if receipt_id:
        extra["receipt_id"] = receipt_id
    if requested_by is None and extra.get("actor_id"):
        requested_by = extra["actor_id"]
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
        result=result,
        failure_reason=failure_reason,
        completed_at=now_utc() if status == "completed" else None,
        **extra,
    )
    doc = r.model_dump()
    doc["created_at"] = doc["created_at"].isoformat()
    t0 = time.monotonic()
    await db.receipts.insert_one(doc)
    RECORDER.receipt_write((time.monotonic() - t0) * 1000)
    doc.pop("_id", None)
    return doc


_CARRIED = ("source", "resident_id", "room", "zone", "conversation_session_id",
            "assigned_role", "assigned_user")


async def update_receipt_status(
    related_object_type: str,
    related_object_id: str,
    status: ReceiptStatus,
    *,
    result: Optional[str] = None,
    failure_reason: Optional[str] = None,
    requested_by: Optional[str] = None,
) -> Optional[dict]:
    """Record a status change for a domain object as a NEW receipt.

    Receipts are never rewritten (ENGINEERING_CONTRACT.md decision 5): the
    receipt that recorded an earlier step keeps saying what it said, and
    this one records the new step. Context (resident, room, session,
    department, assignee) is carried forward from the object's earlier
    receipts.
    Silently no-ops if the object has no receipt yet (older objects predate
    this system) - nothing is invented for them."""
    earlier = await db.receipts.find(
        {"related_object_type": related_object_type, "related_object_id": related_object_id},
        {"_id": 0},
    ).sort("created_at", -1).to_list(200)
    if not earlier:
        return None
    # Newest non-empty value per field: a claim receipt carries no room, so
    # the room comes from the creation receipt, the assignee from the claim.
    prior = {k: next((r[k] for r in earlier if r.get(k)), None) for k in _CARRIED}
    # ...except the assignee, which the latest (un)assign receipt decides.
    assign = next((r for r in earlier if r["action_type"].endswith(("_assigned", "_unassigned"))), None)
    if assign:
        prior["assigned_user"] = assign.get("assigned_user")
    r = Receipt(
        action_type=f"{related_object_type}_{status}",
        related_object_type=related_object_type,
        related_object_id=related_object_id,
        source=prior.get("source") or "system",
        resident_id=prior.get("resident_id"),
        room=prior.get("room"),
        zone=prior.get("zone"),
        conversation_session_id=prior.get("conversation_session_id"),
        requested_by=requested_by,
        assigned_role=prior.get("assigned_role"),
        assigned_user=prior.get("assigned_user"),
        status=status,
        result=result,
        failure_reason=failure_reason,
        acknowledged_at=now_utc() if status == "acknowledged" else None,
        completed_at=now_utc() if status in ("completed", "failed", "cancelled") else None,
    )
    doc = r.model_dump()
    for k in ("created_at", "acknowledged_at", "completed_at"):
        if doc.get(k) is not None:
            doc[k] = doc[k].isoformat()
    await db.receipts.insert_one(doc)
    doc.pop("_id", None)
    return doc


@router.get("")
async def list_receipts(
    resident_id: Optional[str] = None,
    related_object_type: Optional[str] = None,
    related_object_id: Optional[str] = None,
    status: Optional[str] = None,
    action_type: Optional[str] = None,
    source: Optional[str] = None,
    room: Optional[str] = None,
    correlation_id: Optional[str] = None,   # one workflow's receipt chain (SIM-0)
    since: Optional[str] = None,   # ISO; created_at is stored as an ISO string, so a lexical range works (same as routes/events.py)
    until: Optional[str] = None,
    limit: int = Query(200, le=1000),
    user=Depends(require_admin),
):
    q: dict = {}
    for field, val in (
        ("resident_id", resident_id), ("related_object_type", related_object_type),
        ("related_object_id", related_object_id), ("status", status),
        ("action_type", action_type), ("source", source), ("room", room),
        ("correlation_id", correlation_id),
    ):
        if val:
            q[field] = val
    if since or until:
        rng: dict = {}
        if since:
            rng["$gte"] = since
        if until:
            rng["$lte"] = until
        q["created_at"] = rng
    items = await db.receipts.find(q, {"_id": 0}).sort("created_at", -1).to_list(limit)
    return [_iso(i) for i in items]


@router.get("/{receipt_id}")
async def get_receipt(receipt_id: str, user=Depends(require_admin)):
    doc = await db.receipts.find_one({"receipt_id": receipt_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Receipt not found")
    return _iso(doc)
