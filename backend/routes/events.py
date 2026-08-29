"""Canonical event/telemetry log (2026-08-27) - the evidence source of
truth Michael asked for: durable raw facts with actor+context+timestamp,
so anything observable in CAOSCare can be reconstructed, debugged, or
turned into a metric later without having precomputed that metric now.

Other modules call log_event() directly (Python function call, same
pattern as routes/receipts.py's create_receipt()) whenever something
observable happens. The HTTP routes below are read-only query/
reconstruction endpoints - admin-only, since this is largely the same
audience as receipts/audit exports.
"""
from typing import Optional
from fastapi import APIRouter, Depends, Query

from deps import db, require_admin
from models import CaosEvent, EventSource

router = APIRouter(prefix="/events", tags=["events"])


def _iso(doc: dict) -> dict:
    v = doc.get("created_at")
    if v and not isinstance(v, str):
        doc["created_at"] = v.isoformat()
    return doc


async def log_event(
    *,
    event_type: str,
    source: EventSource = "system",
    actor_id: Optional[str] = None,
    actor_role: Optional[str] = None,
    facility_id: Optional[str] = None,
    resident_id: Optional[str] = None,
    room: Optional[str] = None,
    conversation_id: Optional[str] = None,
    request_id: Optional[str] = None,
    admin_section: Optional[str] = None,
    target_type: Optional[str] = None,
    target_id: Optional[str] = None,
    action: Optional[str] = None,
    status: Optional[str] = None,
    duration_ms: Optional[float] = None,
    error_code: Optional[str] = None,
    error_message: Optional[str] = None,
    verification_status: Optional[str] = None,
    receipt_id: Optional[str] = None,
    related_object_type: Optional[str] = None,
    related_object_id: Optional[str] = None,
    metadata: Optional[dict] = None,
) -> dict:
    """Importable helper - never let a logging failure break the caller's
    own operation; the caller's real work always completes regardless of
    whether the event write succeeds."""
    ev = CaosEvent(
        event_type=event_type, source=source, actor_id=actor_id, actor_role=actor_role,
        facility_id=facility_id, resident_id=resident_id, room=room,
        conversation_id=conversation_id, request_id=request_id, admin_section=admin_section,
        target_type=target_type, target_id=target_id, action=action, status=status,
        duration_ms=duration_ms, error_code=error_code, error_message=error_message,
        verification_status=verification_status, receipt_id=receipt_id,
        related_object_type=related_object_type, related_object_id=related_object_id,
        metadata=metadata or {},
    )
    doc = ev.model_dump()
    doc["created_at"] = doc["created_at"].isoformat()
    try:
        await db.events.insert_one(doc)
    except Exception:
        pass
    doc.pop("_id", None)
    return doc


@router.get("")
async def list_events(
    conversation_id: Optional[str] = None,
    request_id: Optional[str] = None,
    resident_id: Optional[str] = None,
    room: Optional[str] = None,
    actor_id: Optional[str] = None,
    event_type: Optional[str] = None,
    target_type: Optional[str] = None,
    target_id: Optional[str] = None,
    since: Optional[str] = None,
    until: Optional[str] = None,
    limit: int = Query(500, le=2000),
    user=Depends(require_admin),
):
    """The generic traceability query seam - start from any conversation,
    resident, room, device, or actor and walk every event that touched it,
    in order. Every future metric/dashboard should be derivable from this
    endpoint's underlying query shape, not a new counter added elsewhere."""
    q: dict = {}
    if conversation_id:
        q["conversation_id"] = conversation_id
    if request_id:
        q["request_id"] = request_id
    if resident_id:
        q["resident_id"] = resident_id
    if room:
        q["room"] = room
    if actor_id:
        q["actor_id"] = actor_id
    if event_type:
        q["event_type"] = event_type
    if target_type:
        q["target_type"] = target_type
    if target_id:
        q["target_id"] = target_id
    if since or until:
        rng: dict = {}
        if since:
            rng["$gte"] = since
        if until:
            rng["$lte"] = until
        q["created_at"] = rng
    items = await db.events.find(q, {"_id": 0}).sort("created_at", 1).to_list(limit)
    return [_iso(i) for i in items]


@router.get("/conversation/{conversation_id}")
async def get_conversation(conversation_id: str, user=Depends(require_admin)):
    """Full chronological reconstruction of one Admin Aria thread - every
    message, tool call, UI action, and their results, in order."""
    items = await db.events.find({"conversation_id": conversation_id}, {"_id": 0}).sort("created_at", 1).to_list(2000)
    return [_iso(i) for i in items]
