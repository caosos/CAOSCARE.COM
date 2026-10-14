"""Synthetic-only cleanup for the ten-resident community burn-in.

Cleanup removes only canonical resident rows whose stable identity and all
simulation markers exactly match the blueprint.  Operational receipts are
append-only evidence and are never deleted.  There is intentionally no route,
startup hook, reset-all operation, task cleanup, worker mutation, or provider
side effect in this module.
"""
from typing import Awaitable, Callable, Optional
import uuid

from routes.actor_context import ActorContext
from simulation.community_blueprint import BURN_IN_RESIDENTS, COMMUNITY_ID, RESIDENTS, SIMULATION_SCOPE
from simulation.community_provisioning import (
    ProvisioningError,
    _collision,
    _marked_for_blueprint,
    _require_operator,
    _simulation_markers,
    _state,
)


REQUEST_ACTION = "simulation_resident_cleanup_requested"
REMOVED_ACTION = "simulation_resident_removed"
RECONCILED_ACTION = "simulation_resident_cleanup_reconciled"
FAILED_ACTION = "simulation_resident_cleanup_failed"
OUTCOME_ACTIONS = (REMOVED_ACTION, RECONCILED_ACTION)
TERMINAL_ACTIONS = (*OUTCOME_ACTIONS, FAILED_ACTION)


class CleanupError(RuntimeError):
    """Cleanup stopped rather than risk deleting real or ambiguous data."""


def _default_store():
    from deps import db

    return db


async def _default_receipt_writer(**kwargs) -> dict:
    from routes.receipts import create_receipt

    return await create_receipt(**kwargs)


def _receipt_matches(receipt: dict) -> bool:
    state = receipt.get("before_state") or {}
    return (
        receipt.get("actor_type") == "real-human"
        and receipt.get("identity_basis") == "authenticated"
        and receipt.get("result_label") in ("simulated", "unverified", "failed")
        and state.get("synthetic") is True
        and state.get("simulation_scope") == SIMULATION_SCOPE
        and state.get("simulation_community_id") == COMMUNITY_ID
    )


async def _receipts(store, resident_id: str, actions: tuple[str, ...]) -> list[dict]:
    rows = await store.receipts.find(
        {
            "related_object_type": "resident",
            "related_object_id": resident_id,
            "action_type": {"$in": list(actions)},
        },
        {"_id": 0},
    ).to_list(50)
    return [row for row in rows if _receipt_matches(row)]


async def _pending_request(store, resident_id: str) -> Optional[dict]:
    requests = await _receipts(store, resident_id, (REQUEST_ACTION,))
    terminals = await _receipts(store, resident_id, TERMINAL_ACTIONS)
    completed_request_ids = {row.get("parent_receipt_id") for row in terminals}
    return next(
        (row for row in requests if row.get("receipt_id") not in completed_request_ids),
        None,
    )


async def _dependent_records(store, recipes) -> list[str]:
    """Name canonical collections that would be orphaned by this cleanup."""
    resident_ids = [recipe.resident_id for recipe in recipes]
    rooms = [recipe.room for recipe in recipes]
    community_marker = {
        "simulation_scope": SIMULATION_SCOPE,
        "simulation_community_id": COMMUNITY_ID,
    }
    checks = (
        ("staff_tasks", {"$or": [
            {"resident_id": {"$in": resident_ids}},
            {"room": {"$in": rooms}},
            community_marker,
        ]}),
        ("notifications", {"$or": [
            {"resident_id": {"$in": resident_ids}},
            {"related_object_type": "resident", "related_object_id": {"$in": resident_ids}},
            community_marker,
        ]}),
        ("sim_runs", {"$or": [
            {"cast.resident.actor_id": {"$in": resident_ids}},
            community_marker,
        ]}),
    )
    found = []
    for collection_name, query in checks:
        collection = getattr(store, collection_name)
        if await collection.find(query, {"_id": 1}).to_list(1):
            found.append(collection_name)
    return found


async def _write_request(
    writer: Callable[..., Awaitable[dict]], operator: ActorContext, authority: str, doc: dict,
    *, simulation_run_id: Optional[str] = None,
) -> dict:
    receipt_id = f"rcpt_{uuid.uuid4().hex[:12]}"
    state = _state(doc)
    return await writer(
        action_type=REQUEST_ACTION,
        related_object_type="resident",
        related_object_id=doc["resident_id"],
        source="staff",
        resident_id=doc["resident_id"],
        room=doc["room"],
        status="created",
        result="synthetic burn-in resident cleanup authorized",
        receipt_id=receipt_id,
        provenance={
            **operator.receipt_fields(),
            **_simulation_markers(simulation_run_id),
            "authority": authority,
            "correlation_id": receipt_id,
            "before_state": state,
            "after_state": state,
            "result_label": "simulated",
            "next_state": "cleanup_pending",
        },
    )


async def _write_outcome(
    writer: Callable[..., Awaitable[dict]], operator: ActorContext, authority: str,
    doc: dict, request: dict, *, action: str, status: str = "completed",
    result_label: str = "simulated", failure_reason: Optional[str] = None,
    simulation_run_id: Optional[str] = None,
) -> dict:
    request_id = request["receipt_id"]
    receipt_id = f"rcpt_{uuid.uuid4().hex[:12]}"
    removed = action in OUTCOME_ACTIONS
    return await writer(
        action_type=action,
        related_object_type="resident",
        related_object_id=doc["resident_id"],
        source="staff",
        resident_id=doc["resident_id"],
        room=doc["room"],
        status=status,
        receipt_id=receipt_id,
        result=(
            "synthetic burn-in resident removed"
            if action == REMOVED_ACTION
            else "resident already absent after a recorded cleanup request"
            if action == RECONCILED_ACTION
            else "synthetic burn-in resident cleanup refused during delete"
        ),
        failure_reason=failure_reason,
        provenance={
            **operator.receipt_fields(),
            **_simulation_markers(simulation_run_id),
            "authority": authority,
            "parent_receipt_id": request_id,
            "correlation_id": request.get("correlation_id") or request_id,
            "before_state": _state(doc),
            "after_state": {
                "resident_id": doc["resident_id"],
                "state": "absent" if removed else "unchanged_or_unknown",
                "synthetic": True,
                "simulation_scope": SIMULATION_SCOPE,
                "simulation_community_id": COMMUNITY_ID,
            },
            "result_label": result_label,
            "next_state": "removed" if action == REMOVED_ACTION else "absence_recorded"
            if action == RECONCILED_ACTION else "manual_review",
        },
    )


async def cleanup_burn_in_residents(
    operator: ActorContext,
    authority: str,
    *,
    store=None,
    receipt_writer: Optional[Callable[..., Awaitable[dict]]] = None,
    simulation_run_id: Optional[str] = None,
    residents=BURN_IN_RESIDENTS,
) -> dict:
    """Remove only the cohort's exactly marked residents, idempotently."""
    try:
        _require_operator(operator, authority)
    except ProvisioningError as exc:
        raise CleanupError(str(exc)) from exc
    store = store if store is not None else _default_store()
    receipt_writer = receipt_writer or _default_receipt_writer
    recipes = tuple(residents)
    if not recipes or any(recipe not in RESIDENTS for recipe in recipes):
        raise CleanupError("cleanup residents must be blueprint residents")

    # All-or-nothing safety preflight: one bad record prevents every delete.
    existing_by_id = {}
    for recipe in recipes:
        try:
            existing = await _collision(store, recipe)
        except ProvisioningError as exc:
            raise CleanupError(str(exc)) from exc
        if existing and not _marked_for_blueprint(existing, recipe):
            raise CleanupError(
                f"resident identity collision for {recipe.resident_id}; existing data was not changed"
            )
        existing_by_id[recipe.resident_id] = existing

    dependencies = await _dependent_records(store, recipes)
    if dependencies:
        joined = ", ".join(dependencies)
        raise CleanupError(f"residents have dependent records in {joined}; cleanup refused")

    removed_ids, already_absent_ids, reconciled_ids, receipts = [], [], [], []
    for recipe in recipes:
        doc = existing_by_id[recipe.resident_id]
        outcomes = await _receipts(store, recipe.resident_id, OUTCOME_ACTIONS)
        if not doc:
            if outcomes:
                already_absent_ids.append(recipe.resident_id)
                receipts.append(outcomes[0])
                continue
            request = await _pending_request(store, recipe.resident_id)
            if request:
                # Truthful recovery after a crash between delete and completion
                # receipt: absence is proven; who performed the delete is not.
                receipt = await _write_outcome(
                    receipt_writer, operator, authority,
                    {**_state_from_recipe(recipe)}, request, action=RECONCILED_ACTION,
                    result_label="unverified", simulation_run_id=simulation_run_id,
                )
                reconciled_ids.append(recipe.resident_id)
                receipts.append(receipt)
            else:
                already_absent_ids.append(recipe.resident_id)
            continue

        request = await _pending_request(store, recipe.resident_id)
        request = request or await _write_request(
            receipt_writer, operator, authority, doc,
            simulation_run_id=simulation_run_id,
        )
        result = await store.residents.delete_one({
            "resident_id": recipe.resident_id,
            "room": recipe.room,
            "pendant_id": recipe.pendant_id,
            "synthetic": True,
            "simulation_scope": SIMULATION_SCOPE,
            "simulation_community_id": COMMUNITY_ID,
        })
        if result.deleted_count != 1:
            await _write_outcome(
                receipt_writer, operator, authority, doc, request, action=FAILED_ACTION,
                status="failed", result_label="failed",
                failure_reason="resident changed after preflight; nothing was deleted",
                simulation_run_id=simulation_run_id,
            )
            raise CleanupError(
                f"resident {recipe.resident_id} changed after preflight; cleanup stopped"
            )
        receipt = await _write_outcome(
            receipt_writer, operator, authority, doc, request, action=REMOVED_ACTION,
            simulation_run_id=simulation_run_id,
        )
        removed_ids.append(recipe.resident_id)
        receipts.append(receipt)

    return {
        "community_id": COMMUNITY_ID,
        "removed_ids": removed_ids,
        "already_absent_ids": already_absent_ids,
        "reconciled_ids": reconciled_ids,
        "receipts": receipts,
    }


def _state_from_recipe(recipe) -> dict:
    return {
        "resident_id": recipe.resident_id,
        "room": recipe.room,
        "pendant_id": recipe.pendant_id,
        "synthetic": True,
        "simulation_scope": SIMULATION_SCOPE,
        "simulation_community_id": COMMUNITY_ID,
    }
