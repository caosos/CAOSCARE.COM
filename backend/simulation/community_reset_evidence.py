"""Deterministic receipt evidence for living-community reset transactions."""

from datetime import datetime
from typing import Optional

from models import Receipt
from routes.actor_context import ActorContext
from simulation.community_blueprint import COMMUNITY_ID, SIMULATION_SCOPE


REQUEST_ACTION = "simulation_community_reset_requested"
OUTCOME_ACTION = "simulation_community_reset_completed"
REPLAY_ACTION = "simulation_community_reset_replayed"
RESET_COLLECTIONS = ("residents", "staff_tasks", "notifications", "sim_runs")


class ResetEvidenceError(RuntimeError):
    """Durable reset evidence is incomplete or internally inconsistent."""


def receipt_id(reset_id: str, phase: str) -> str:
    return f"rcpt:{reset_id}:{phase}"


async def load_reset_receipts(store, session, reset_id: str) -> list[dict]:
    cursor = store.receipts.find(
        {
            "related_object_type": "simulation_community_reset",
            "related_object_id": reset_id,
        },
        None,
        session=session,
    )
    rows = await cursor.to_list(None)
    if any(
        row.get("simulation_scope") != SIMULATION_SCOPE
        or row.get("simulation_community_id") != COMMUNITY_ID
        for row in rows
    ):
        raise ResetEvidenceError("reset evidence has partial or mismatched scope")
    return rows


def snapshot(rows: dict[str, list[dict]], receipt_count: int) -> dict:
    return {
        "simulation_scope": SIMULATION_SCOPE,
        "simulation_community_id": COMMUNITY_ID,
        "counts": {name: len(rows[name]) for name in RESET_COLLECTIONS},
        "preserved_receipts": receipt_count,
    }


def build_receipt(
    action: str,
    reset_id: str,
    operator: ActorContext,
    authority: str,
    generation: int,
    before: dict,
    after: dict,
    when: datetime,
    *,
    parent: Optional[str] = None,
) -> dict:
    phase = {
        REQUEST_ACTION: "request",
        OUTCOME_ACTION: "outcome",
        REPLAY_ACTION: "replay",
    }[action]
    identifier = receipt_id(reset_id, phase)
    doc = Receipt(
        receipt_id=identifier,
        action_type=action,
        related_object_type="simulation_community_reset",
        related_object_id=reset_id,
        source="staff",
        status="created" if action == REQUEST_ACTION else "completed",
        completed_at=None if action == REQUEST_ACTION else when,
        result=(
            "reset authorized" if action == REQUEST_ACTION else
            "idempotent reset retry observed" if action == REPLAY_ACTION else
            "living-community data reset transaction committed"
        ),
        **operator.receipt_fields(),
        simulation_scope=SIMULATION_SCOPE,
        simulation_community_id=COMMUNITY_ID,
        authority=authority,
        parent_receipt_id=parent,
        correlation_id=receipt_id(reset_id, "request"),
        before_state={**before, "reset_generation": generation},
        after_state={**after, "reset_generation": generation},
        result_label="simulated",
        next_state="reset_pending" if action == REQUEST_ACTION else "reset_complete",
        created_at=when,
    ).model_dump()
    doc["_id"] = identifier
    doc["created_at"] = doc["created_at"].isoformat()
    if doc.get("completed_at") is not None:
        doc["completed_at"] = doc["completed_at"].isoformat()
    return doc


def committed_result(
    reset_id: str,
    reset_receipts: list[dict],
    current_rows: dict[str, list[dict]],
) -> Optional[dict]:
    """Return the proven committed result, None, or reject partial evidence."""
    by_phase = {}
    expected = {
        REQUEST_ACTION: receipt_id(reset_id, "request"),
        OUTCOME_ACTION: receipt_id(reset_id, "outcome"),
        REPLAY_ACTION: receipt_id(reset_id, "replay"),
    }
    for row in reset_receipts:
        action = row.get("action_type")
        if action not in expected or action in by_phase:
            raise ResetEvidenceError("duplicate or unknown reset evidence requires manual review")
        if row.get("_id") != expected[action] or row.get("receipt_id") != expected[action]:
            raise ResetEvidenceError("reset evidence lacks its deterministic identity")
        by_phase[action] = row
    outcome = by_phase.get(OUTCOME_ACTION)
    if not outcome:
        if by_phase:
            raise ResetEvidenceError("incomplete reset evidence requires manual review")
        return None
    request = by_phase.get(REQUEST_ACTION)
    after = outcome.get("after_state") or {}
    before = outcome.get("before_state") or {}
    generation = after.get("reset_generation")
    expected_counts = {name: 0 for name in RESET_COLLECTIONS}
    if (
        not request
        or outcome.get("parent_receipt_id") != request.get("receipt_id")
        or request.get("correlation_id") != request.get("receipt_id")
        or outcome.get("correlation_id") != request.get("receipt_id")
        or not isinstance(generation, int)
        or generation < 1
        or after.get("counts") != expected_counts
        or any(current_rows[name] for name in RESET_COLLECTIONS)
    ):
        raise ResetEvidenceError("reset outcome is not proven by exact receipt and state evidence")
    deleted = before.get("counts")
    if not isinstance(deleted, dict) or any(
        not isinstance(deleted.get(name), int) or deleted[name] < 0
        for name in RESET_COLLECTIONS
    ):
        raise ResetEvidenceError("reset outcome has invalid before-state evidence")
    return {
        "reset_id": reset_id,
        "reset_generation": generation,
        "idempotent_replay": REPLAY_ACTION in by_phase,
        "receipt_id": (
            expected[REPLAY_ACTION] if REPLAY_ACTION in by_phase else expected[OUTCOME_ACTION]
        ),
        "deleted": dict(deleted),
    }
