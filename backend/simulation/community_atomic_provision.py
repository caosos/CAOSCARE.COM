"""Atomic resident-readiness gate for one living-community burn-in run.

This service writes no route and selects no default database.  The exact
PAUSED run, ten canonical residents, their run-bound receipts, and the run's
resident-readiness marker commit in one required transaction.
"""
from datetime import datetime, timezone
from hashlib import sha256
from typing import Optional
from models import Receipt
from pymongo import ReturnDocument
from routes.actor_context import ActorContext
from simulation.community_blueprint import COMMUNITY_ID, SIMULATION_SCOPE
from simulation.community_cohort import residents_for
from simulation.community_provisioning import (
    ADMIN_ROLES,
    PROVISION_ACTION,
    RECONCILE_ACTION,
    ProvisioningError,
    _require_operator,
    provision_burn_in_residents,
)
from simulation.community_run_lifecycle import PAUSED, RUN_KIND
from simulation.community_timeline import CommunityTimeline, validate_timeline
READY_ACTION = "simulation_community_resident_provisioning_completed"
RESIDENT_ACTIONS = (PROVISION_ACTION, RECONCILE_ACTION)

class CommunityAtomicProvisionError(RuntimeError):
    """The exact run cannot be made resident-ready without ambiguity."""

def _key(value: str) -> tuple[str, str]:
    clean = (value or "").strip()
    if not clean or len(clean) > 160:
        raise CommunityAtomicProvisionError(
            "a stable idempotency key of 1-160 characters is required"
        )
    return clean, sha256(clean.encode()).hexdigest()

def _instant(value: Optional[datetime]) -> datetime:
    instant = value or datetime.now(timezone.utc)
    if instant.tzinfo is None:
        raise CommunityAtomicProvisionError("provisioning timestamps must be timezone-aware")
    return instant.astimezone(timezone.utc)


def _plan_fields(plan: CommunityTimeline) -> dict:
    try:
        checked = validate_timeline(plan)
    except (TypeError, ValueError) as exc:
        raise CommunityAtomicProvisionError("the canonical timeline is invalid") from exc
    return {"plan_revision": checked.plan_revision, "plan_digest_sha256": checked.digest_sha256,
            "event_count": checked.event_count, "timeline_end_minute": checked.day_count * 1440 - 1}


def _scope(run_id: str) -> dict:
    return {
        "run_id": run_id,
        "simulation_scope": SIMULATION_SCOPE,
        "simulation_community_id": COMMUNITY_ID,
        "run_kind": RUN_KIND,
    }


def _snapshot(row: dict) -> dict:
    fields = (
        "run_id", "state", "cursor", "sim_minute", "plan_revision",
        "plan_digest_sha256", "event_count", "timeline_end_minute",
        "simulation_scope", "simulation_community_id", "run_kind",
        "residents_provisioned", "provisioning_receipt_id",
        "provisioning_resident_receipt_ids", "provisioning_created_ids",
        "provisioning_reused_ids",
    )
    return {field: row.get(field) for field in fields}


def _readiness_id(run_id: str, key_digest: str) -> str:
    digest = sha256(f"{run_id}:{key_digest}:residents-ready".encode()).hexdigest()[:24]
    return f"rcpt:simrun-provision:{digest}"


async def _one_run(store, run_id: str, session) -> dict:
    rows = await store.sim_runs.find({"run_id": run_id}, {"_id": 0}, session=session).to_list(None)
    expected = _scope(run_id)
    if len(rows) != 1 or any(rows[0].get(k) != value for k, value in expected.items()):
        raise CommunityAtomicProvisionError(
            "run scope is missing, ambiguous, or conflicts with another run"
        )
    return rows[0]


def _exact_run(
    row: dict, plan_fields: dict, expected_cursor: int,
    expected_sim_minute: int, *, provisioned: bool, residents: tuple,
) -> None:
    expected = {
        **plan_fields, "state": PAUSED, "cursor": expected_cursor,
        "sim_minute": expected_sim_minute, "resident_count": len(residents),
        "residents_provisioned": provisioned,
    }
    if any(row.get(key) != value for key, value in expected.items()):
        raise CommunityAtomicProvisionError(
            "exact PAUSED run plan, cursor, clock, or resident state is stale"
        )
    if "execution_lease" in row:
        raise CommunityAtomicProvisionError("resident provisioning requires an unleased run")


async def _resident_receipts(store, run_id: str, session, residents: tuple) -> list[dict]:
    rows = await store.receipts.find({
        "related_object_type": "resident",
        "related_object_id": {"$in": [row.resident_id for row in residents]},
        "action_type": {"$in": list(RESIDENT_ACTIONS)},
        "simulation_run_id": run_id,
        "simulation_scope": SIMULATION_SCOPE,
        "simulation_community_id": COMMUNITY_ID,
    }, {"_id": 0}, session=session).to_list(None)
    expected_ids = {row.resident_id for row in residents}
    by_resident = {row.get("related_object_id"): row for row in rows}
    if len(rows) != len(residents) or set(by_resident) != expected_ids:
        raise CommunityAtomicProvisionError(
            "current-run resident receipts are missing, duplicated, or out of scope"
        )
    return [by_resident[row.resident_id] for row in residents]


def _validate_resident_receipts(
    rows: list[dict], run: dict, authority: str, residents: tuple,
) -> list[str]:
    parent = run.get("last_transition_receipt_id")
    correlation = run.get("origin_receipt_id")
    identifiers = []
    for recipe, row in zip(residents, rows):
        after = row.get("after_state") or {}
        if (
            row.get("actor_type") != "real-human"
            or not row.get("actor_id")
            or row.get("identity_basis") != "authenticated"
            or row.get("simulated") is not False
            or row.get("actor_role") not in ADMIN_ROLES
            or row.get("authority") != authority
            or row.get("parent_receipt_id") != parent
            or row.get("correlation_id") != correlation
            or row.get("status") != "completed"
            or row.get("result_label") != "simulated"
            or after.get("resident_id") != recipe.resident_id
            or after.get("room") != recipe.room
            or after.get("pendant_id") != recipe.pendant_id
            or after.get("synthetic") is not True
            or after.get("simulation_scope") != SIMULATION_SCOPE
            or after.get("simulation_community_id") != COMMUNITY_ID
            or (row.get("action_type") == PROVISION_ACTION and row.get("before_state") is not None)
            or (row.get("action_type") == RECONCILE_ACTION and row.get("before_state") != after)
        ):
            raise CommunityAtomicProvisionError(
                f"resident receipt provenance is incomplete for {recipe.resident_id}"
            )
        identifier = row.get("receipt_id")
        if not identifier or identifier in identifiers:
            raise CommunityAtomicProvisionError("resident receipt identities are invalid")
        identifiers.append(identifier)
    return identifiers


def _ready_receipt(
    run: dict, changed: dict, operator: ActorContext, authority: str,
    identifier: str, key_digest: str, instant: datetime,
) -> dict:
    doc = Receipt(
        receipt_id=identifier,
        action_type=READY_ACTION,
        related_object_type="simulation_run",
        related_object_id=run["run_id"],
        source="staff",
        requested_by=operator.actor_id,
        status="completed",
        completed_at=instant,
        result="ten canonical burn-in residents committed for this exact run",
        **operator.receipt_fields(),
        simulation_scope=SIMULATION_SCOPE,
        simulation_community_id=COMMUNITY_ID,
        simulation_run_id=run["run_id"],
        authority=authority,
        parent_receipt_id=run.get("last_transition_receipt_id"),
        correlation_id=run.get("origin_receipt_id"),
        before_state=_snapshot(run),
        after_state=_snapshot(changed),
        result_label="simulated",
        next_state="resident_gate_ready",
        created_at=instant,
    ).model_dump()
    doc.update(_id=identifier, idempotency_key_sha256=key_digest)
    for field in ("created_at", "completed_at"):
        doc[field] = doc[field].isoformat()
    return doc


async def _replay(
    store, run: dict, run_id: str, operator: ActorContext, authority: str, identifier: str,
    key_digest: str, plan_fields: dict, expected_cursor: int,
    expected_sim_minute: int, session, residents: tuple,
) -> dict:
    _exact_run(run, plan_fields, expected_cursor, expected_sim_minute,
               provisioned=True, residents=residents)
    receipt = await store.receipts.find_one({"_id": identifier}, {"_id": 0}, session=session)
    rows = await _resident_receipts(store, run_id, session, residents)
    ids = _validate_resident_receipts(rows, run, authority, residents)
    if (
        not receipt
        or receipt.get("action_type") != READY_ACTION
        or receipt.get("idempotency_key_sha256") != key_digest
        or receipt.get("actor_id") != operator.actor_id
        or receipt.get("actor_role") != operator.role
        or receipt.get("identity_basis") != "authenticated"
        or receipt.get("authority") != authority
        or receipt.get("after_state") != _snapshot(run)
        or run.get("provisioning_receipt_id") != identifier
        or run.get("provisioning_resident_receipt_ids") != ids
    ):
        raise CommunityAtomicProvisionError("resident provisioning replay evidence conflicts")
    return {"run": run, "receipt": receipt, "resident_receipts": rows,
            "created_ids": run.get("provisioning_created_ids", []),
            "reused_ids": run.get("provisioning_reused_ids", []),
            "idempotent_replay": True}


async def provision_paused_burn_in_run(
    operator: ActorContext, authority: str, run_id: str,
    expected_cursor: int, expected_sim_minute: int, operation_key: str,
    plan: CommunityTimeline, *, store, now: Optional[datetime] = None,
) -> dict:
    """Commit the plan cohort's residents and run-bound readiness evidence atomically."""
    try:
        _require_operator(operator, authority)
    except ProvisioningError as exc:
        raise CommunityAtomicProvisionError(str(exc)) from exc
    if any(
        not isinstance(value, int) or isinstance(value, bool) or value < 0
        for value in (expected_cursor, expected_sim_minute)
    ):
        raise CommunityAtomicProvisionError("cursor and clock must be non-negative integers")
    _, key_digest = _key(operation_key)
    plan_fields, instant = _plan_fields(plan), _instant(now)
    residents = residents_for(plan.cohort)
    identifier = _readiness_id(run_id, key_digest)
    client = getattr(store, "client", None)
    if client is None or not callable(getattr(client, "start_session", None)):
        raise CommunityAtomicProvisionError("transaction-capable injected storage is required")
    async with await client.start_session() as session:
        async with session.start_transaction():
            run = await _one_run(store, run_id, session)
            if run.get("residents_provisioned") is True:
                return await _replay(
                    store, run, run_id, operator, authority, identifier, key_digest,
                    plan_fields, expected_cursor, expected_sim_minute, session, residents,
                )
            _exact_run(run, plan_fields, expected_cursor, expected_sim_minute,
                       provisioned=False, residents=residents)
            try:
                result = await provision_burn_in_residents(
                    operator, authority, store=store, simulation_run_id=run_id, residents=residents,
                    session=session, parent_receipt_id=run.get("last_transition_receipt_id"),
                    correlation_id=run.get("origin_receipt_id"), now=instant,
                )
            except ProvisioningError as exc:
                raise CommunityAtomicProvisionError(str(exc)) from exc
            rows = await _resident_receipts(store, run_id, session, residents)
            resident_receipt_ids = _validate_resident_receipts(rows, run, authority, residents)
            updates = {
                "residents_provisioned": True,
                "provisioning_receipt_id": identifier,
                "provisioning_resident_receipt_ids": resident_receipt_ids,
                "provisioning_created_ids": result["created_ids"],
                "provisioning_reused_ids": result["reused_ids"],
                "updated_at": instant.isoformat(),
            }
            changed = await store.sim_runs.find_one_and_update(
                {**_scope(run_id), **plan_fields, "state": PAUSED,
                 "cursor": expected_cursor, "sim_minute": expected_sim_minute,
                 "residents_provisioned": False,
                 "execution_lease": {"$exists": False}},
                {"$set": updates}, projection={"_id": 0}, session=session,
                return_document=ReturnDocument.AFTER,
            )
            if not changed:
                raise CommunityAtomicProvisionError("run changed during resident provisioning")
            receipt = _ready_receipt(
                run, changed, operator, authority, identifier, key_digest, instant,
            )
            await store.receipts.insert_one(receipt, session=session)
            receipt.pop("_id", None)
            return {"run": changed, "receipt": receipt, "resident_receipts": rows,
                    "created_ids": result["created_ids"],
                    "reused_ids": result["reused_ids"],
                    "idempotent_replay": False}
