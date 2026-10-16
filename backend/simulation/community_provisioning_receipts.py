"""Canonical receipt documents for living-community resident provisioning."""

from datetime import datetime, timezone
from hashlib import sha256
from typing import Optional
import uuid

from models import Receipt
from routes.actor_context import ActorContext
from simulation.community_blueprint import COMMUNITY_ID, SIMULATION_SCOPE


def resident_receipt_id(
    resident_id: str, action: str, simulation_run_id: Optional[str],
) -> str:
    if not simulation_run_id:
        return f"rcpt_{uuid.uuid4().hex[:12]}"
    digest = sha256(
        f"{simulation_run_id}:{resident_id}:{action}".encode()
    ).hexdigest()[:24]
    return f"rcpt:simresident:{digest}"


def build_resident_receipt(
    *, action: str, resident: dict, created: bool, operator: ActorContext,
    authority: str, simulation_run_id: Optional[str],
    parent_receipt_id: Optional[str] = None,
    correlation_id: Optional[str] = None,
    now: Optional[datetime] = None,
) -> dict:
    instant = now or datetime.now(timezone.utc)
    if instant.tzinfo is None:
        raise ValueError("provisioning receipt timestamps must be timezone-aware")
    instant = instant.astimezone(timezone.utc)
    identifier = resident_receipt_id(
        resident["resident_id"], action, simulation_run_id,
    )
    state = {
        key: resident.get(key)
        for key in (
            "resident_id", "room", "pendant_id", "synthetic",
            "simulation_scope", "simulation_community_id",
        )
    }
    doc = Receipt(
        receipt_id=identifier,
        action_type=action,
        related_object_type="resident",
        related_object_id=resident["resident_id"],
        source="staff",
        resident_id=resident["resident_id"],
        room=resident["room"],
        status="completed",
        completed_at=instant,
        result=(
            "created synthetic burn-in resident" if created
            else "reconciled existing synthetic burn-in resident"
        ),
        **operator.receipt_fields(),
        simulation_scope=SIMULATION_SCOPE,
        simulation_community_id=COMMUNITY_ID,
        simulation_run_id=simulation_run_id,
        authority=authority,
        parent_receipt_id=parent_receipt_id,
        correlation_id=correlation_id or identifier,
        before_state=None if created else state,
        after_state=state,
        result_label="simulated",
        next_state="ready_for_burn_in",
        created_at=instant,
    ).model_dump()
    doc["_id"] = identifier
    for field in ("created_at", "completed_at"):
        doc[field] = doc[field].isoformat()
    return doc
