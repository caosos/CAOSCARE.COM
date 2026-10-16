"""Deterministic provenance receipts for simulator index preparation."""

from datetime import datetime
from hashlib import sha256
import json

from models import Receipt
from routes.actor_context import ActorContext
from simulation.community_blueprint import COMMUNITY_ID, SIMULATION_SCOPE
from simulation.community_index_contract import REQUIRED_INDEXES


REQUESTED = "simulation_indexes_requested"
COMPLETED = "simulation_indexes_completed"
FAILED = "simulation_indexes_failed"
RECONCILED = "simulation_indexes_reconciled"
OUTCOMES = (COMPLETED, FAILED, RECONCILED)
SYSTEM_ACTOR = ActorContext(
    actor_id="system:living-community-index-preparer",
    actor_type="system",
    identity_basis="system",
    channel="system",
    name="Living Community Index Preparer",
    role="system",
    simulated=False,
)


class IndexEvidenceError(RuntimeError):
    """Index preparation evidence is missing, conflicting, or ambiguous."""


def contract_snapshot() -> list[dict]:
    return [
        {
            "collection": row["collection"], "name": row["name"],
            "keys": [list(item) for item in row["keys"]],
            "unique": row["unique"], "purpose": row["purpose"],
        }
        for row in REQUIRED_INDEXES
    ]


def contract_digest() -> str:
    encoded = json.dumps(contract_snapshot(), sort_keys=True, separators=(",", ":"))
    return sha256(encoded.encode()).hexdigest()


def operation_identity(operation_key: str) -> tuple[str, str]:
    clean = operation_key.strip() if isinstance(operation_key, str) else ""
    if not clean or len(clean) > 160:
        raise IndexEvidenceError("a stable operation key of 1-160 characters is required")
    digest = sha256(clean.encode()).hexdigest()
    return f"simindex:{digest[:24]}", digest


def receipt_id(operation_id: str, action: str) -> str:
    phase = {
        REQUESTED: "requested", COMPLETED: "completed",
        FAILED: "failed", RECONCILED: "reconciled",
    }[action]
    return f"rcpt:{operation_id}:{phase}"


def build_receipt(
    action: str, operation_id: str, key_digest: str, operator: ActorContext,
    authority: str, before: dict, after: dict, when: datetime,
    *, failure_reason: str | None = None,
) -> dict:
    identifier = receipt_id(operation_id, action)
    requested_id = receipt_id(operation_id, REQUESTED)
    actor = operator if action == REQUESTED else SYSTEM_ACTOR
    status = "created" if action == REQUESTED else "failed" if action == FAILED else "completed"
    result = {
        REQUESTED: "simulator index preparation authorized",
        COMPLETED: "required simulator indexes created and verified",
        FAILED: "simulator index preparation failed closed",
        RECONCILED: "required simulator indexes verified after an interrupted or ambiguous attempt",
    }[action]
    doc = Receipt(
        receipt_id=identifier,
        action_type=action,
        related_object_type="simulation_index_preparation",
        related_object_id=operation_id,
        source="staff" if action == REQUESTED else "system",
        status=status,
        completed_at=None if action == REQUESTED else when,
        result=result,
        failure_reason=failure_reason,
        requested_by=operator.actor_id,
        **actor.receipt_fields(),
        simulation_scope=SIMULATION_SCOPE,
        simulation_community_id=COMMUNITY_ID,
        authority=authority,
        parent_receipt_id=None if action == REQUESTED else requested_id,
        correlation_id=requested_id,
        before_state=before,
        after_state=after,
        result_label="unverified" if action == REQUESTED else "failed" if action == FAILED else "verified",
        next_state="preparation_pending" if action == REQUESTED else "preparation_failed" if action == FAILED else "indexes_ready",
        created_at=when,
    ).model_dump()
    doc.update(
        _id=identifier,
        operation_key_sha256=key_digest,
        index_contract_sha256=contract_digest(),
    )
    for field in ("created_at", "completed_at"):
        if doc.get(field) is not None:
            doc[field] = doc[field].isoformat()
    return doc


async def load_receipts(store, operation_id: str, *, session=None) -> list[dict]:
    cursor = store.receipts.find({
        "related_object_type": "simulation_index_preparation",
        "related_object_id": operation_id,
    }, None, session=session)
    return await cursor.to_list(None)


def validate_receipts(
    rows: list[dict], operation_id: str, key_digest: str,
    operator: ActorContext, authority: str,
) -> dict:
    by_action = {}
    allowed = (REQUESTED, *OUTCOMES)
    for row in rows:
        action = row.get("action_type")
        if action not in allowed or action in by_action:
            raise IndexEvidenceError("duplicate or unknown index preparation evidence")
        expected_id = receipt_id(operation_id, action)
        if (
            row.get("_id") != expected_id
            or row.get("receipt_id") != expected_id
            or row.get("related_object_type") != "simulation_index_preparation"
            or row.get("related_object_id") != operation_id
            or row.get("simulation_scope") != SIMULATION_SCOPE
            or row.get("simulation_community_id") != COMMUNITY_ID
            or row.get("operation_key_sha256") != key_digest
            or row.get("index_contract_sha256") != contract_digest()
            or row.get("correlation_id") != receipt_id(operation_id, REQUESTED)
            or row.get("authority") != authority
            or row.get("simulated") is not False
        ):
            raise IndexEvidenceError("index preparation evidence has invalid identity or provenance")
        by_action[action] = row
    request = by_action.get(REQUESTED)
    if request and (
        request.get("actor_id") != operator.actor_id
        or request.get("requested_by") != operator.actor_id
        or request.get("actor_type") != "real-human"
        or request.get("identity_basis") != "authenticated"
        or request.get("parent_receipt_id") is not None
        or request.get("status") != "created"
    ):
        raise IndexEvidenceError("operation key belongs to another authenticated request")
    outcomes = [by_action[action] for action in OUTCOMES if action in by_action]
    if len(outcomes) > 1 or (outcomes and not request):
        raise IndexEvidenceError("index preparation outcome evidence is ambiguous")
    if outcomes and (
        outcomes[0].get("parent_receipt_id") != receipt_id(operation_id, REQUESTED)
        or outcomes[0].get("requested_by") != operator.actor_id
        or outcomes[0].get("actor_id") != SYSTEM_ACTOR.actor_id
        or outcomes[0].get("actor_type") != "system"
        or outcomes[0].get("identity_basis") != "system"
        or outcomes[0].get("status") != (
            "failed" if outcomes[0].get("action_type") == FAILED else "completed"
        )
    ):
        raise IndexEvidenceError("index preparation outcome lacks system provenance")
    return {"request": request, "outcome": outcomes[0] if outcomes else None}
