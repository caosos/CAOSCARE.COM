"""Receipt construction for atomic living-community run transitions."""

from datetime import datetime
from hashlib import sha256
from typing import Optional

from models import Receipt
from routes.actor_context import ActorContext
from simulation.community_blueprint import COMMUNITY_ID, SIMULATION_SCOPE


SNAPSHOT_FIELDS = (
    "run_id",
    "state",
    "cursor",
    "sim_minute",
    "plan_revision",
    "plan_digest_sha256",
    "event_count",
    "timeline_end_minute",
    "simulation_scope",
    "simulation_community_id",
    "run_kind",
    "original_human_starter",
    "terminal_reason",
    "completed_at",
    "completion_receipt_id",
    "last_event_id",
    "last_evidence_receipt_id",
    "last_evidence_status",
)


def snapshot(row: dict) -> dict:
    return {key: row.get(key) for key in SNAPSHOT_FIELDS}


def receipt_id(run_id: str, key_digest: str) -> str:
    digest = sha256(f"{run_id}:{key_digest}".encode()).hexdigest()[:24]
    return f"rcpt:simrun:{digest}"


def build_receipt(
    action: str,
    receipt_id_value: str,
    key_digest: str,
    row: dict,
    operator: ActorContext,
    authority: str,
    when: datetime,
    before: Optional[dict],
    after: dict,
) -> dict:
    parent = row.get("last_transition_receipt_id") if before else None
    correlation = row.get("origin_receipt_id") or receipt_id_value
    doc = Receipt(
        receipt_id=receipt_id_value,
        action_type=action,
        related_object_type="simulation_run",
        related_object_id=row["run_id"],
        source="system" if operator.actor_type == "system" else "staff",
        status="completed",
        result="living-community run lifecycle transition committed",
        completed_at=when,
        **operator.receipt_fields(),
        simulation_scope=SIMULATION_SCOPE,
        simulation_community_id=COMMUNITY_ID,
        simulation_run_id=row["run_id"],
        authority=authority,
        parent_receipt_id=parent,
        correlation_id=correlation,
        before_state=before,
        after_state=after,
        result_label="simulated",
        next_state=after["state"].lower(),
        created_at=when,
    ).model_dump()
    doc.update(_id=receipt_id_value, idempotency_key_sha256=key_digest)
    for field in ("created_at", "completed_at"):
        doc[field] = doc[field].isoformat()
    return doc
