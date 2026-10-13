"""Explicit, isolated direct-Mongo acceptance for the living community.

Nothing runs at import or startup. The caller must supply an already validated,
pristine scratch database and an explicit reopen callback. All mutations flow
through the receipt-backed simulator services used by the application.
"""

import inspect
from datetime import datetime, timezone

from routes.actor_context import ActorContext
from simulation import community_run_lifecycle as lifecycle
from simulation.community_atomic_provision import provision_paused_burn_in_run
from simulation.community_blueprint import COMMUNITY_ID, SIMULATION_SCOPE
from simulation.community_control_service import runner_actor
from simulation.community_execution_adapter import CanonicalCommunityExecutionServices
from simulation.community_index_preparation import prepare_required_indexes
from simulation.community_mongo_probe import (
    CommunityMongoAcceptanceError,
    probe_mongo,
    require_pristine_scratch,
    validate_scratch_database,
)
from simulation.community_reset import reset_living_community
from simulation.community_runner import tick
from simulation.community_runner_timeline import DatabaseRunnerTimeline, canonical_plan
from simulation import community_ticket_staging as ticket_staging


AUTHORITY = "admin_override:owner"
HOLDER_ID = "operator-cli:direct-mongo-acceptance"


def _operator(operator_id: str, operator_name: str | None) -> ActorContext:
    identifier = operator_id.strip() if isinstance(operator_id, str) else ""
    if not identifier or len(identifier) > 160:
        raise CommunityMongoAcceptanceError("operator-id must contain 1-160 characters")
    return ActorContext(
        actor_id=identifier,
        actor_type="real-human",
        identity_basis="authenticated",
        channel="operator_cli",
        name=(operator_name or "Direct Mongo acceptance operator").strip(),
        role="owner",
        simulated=False,
    )


def _key(database_name: str, phase: str) -> str:
    return f"direct-mongo:{database_name}:{phase}"


def _event_minute(event) -> int:
    return event.day_index * 1440 + event.minute


async def _reopen(callback):
    value = callback()
    return await value if inspect.isawaitable(value) else value


async def _advance_and_tick(store, plan, run: dict, phase: str, now: datetime) -> dict:
    canonical_store = ticket_staging.default_store()
    if getattr(canonical_store, "name", None) != store.name:
        raise CommunityMongoAcceptanceError(
            "canonical task services are not bound to the validated scratch database"
        )
    timeline = DatabaseRunnerTimeline(store=store, plan=plan)
    event = timeline.event_at(run["cursor"])
    if event is None:
        raise CommunityMongoAcceptanceError("canonical plan has no event to execute")
    target = _event_minute(event)
    if target > run["sim_minute"]:
        advanced = await lifecycle.advance_simulated_clock(
            runner_actor(), f"simulation_run:{run['run_id']}:clock",
            run["run_id"], run["cursor"], run["sim_minute"], target,
            _key(store.name, f"{phase}-clock"), plan, store=store, now=now,
        )
        run = advanced["run"]
    result = await tick(
        run["run_id"], HOLDER_ID, store=store, timeline=timeline,
        services=CanonicalCommunityExecutionServices(store=store), now=now,
    )
    if result.status != "executed" or result.cursor_after != run["cursor"] + 1:
        raise CommunityMongoAcceptanceError("one canonical event did not execute exactly once")
    current = await timeline.load_run(run_id=run["run_id"])
    return {"run": current, "tick": result}


async def _verify_reset(store, reset_result: dict) -> dict:
    exact = {
        "simulation_scope": SIMULATION_SCOPE,
        "simulation_community_id": COMMUNITY_ID,
    }
    counts = {}
    for name in ("sim_runs", "residents", "staff_tasks", "notifications"):
        counts[name] = await getattr(store, name).count_documents(exact)
    if any(counts.values()):
        raise CommunityMongoAcceptanceError("reset left scoped mutable rows in scratch storage")
    receipt_count = await store.receipts.count_documents(exact)
    if receipt_count < 1 or not reset_result.get("receipt_id"):
        raise CommunityMongoAcceptanceError("reset left no durable receipt evidence")
    return {"mutable_counts": counts, "preserved_receipts": receipt_count}


async def run_scratch_acceptance(
    store,
    *,
    database_name: str,
    production_databases,
    confirmed: bool,
    operator_id: str,
    operator_name: str | None,
    reopen_store,
    now: datetime | None = None,
) -> dict:
    """Provision, execute, pause, reconnect, resume, execute, stop and reset."""
    database_name = validate_scratch_database(
        database_name, production_db=production_databases, confirmed=confirmed,
    )
    await require_pristine_scratch(store, database_name)
    probe = await probe_mongo(store)
    if probe["status"] != "passed":
        raise CommunityMongoAcceptanceError(
            f"scratch MongoDB transaction gate failed ({probe['error_type']})"
        )
    instant = now or datetime.now(timezone.utc)
    if instant.tzinfo is None:
        raise CommunityMongoAcceptanceError("acceptance timestamp must be timezone-aware")
    operator = _operator(operator_id, operator_name)
    plan = canonical_plan()

    indexes = await prepare_required_indexes(
        operator, AUTHORITY, _key(database_name, "indexes"), store=store, now=instant,
    )
    if indexes["status"] != "ready":
        raise CommunityMongoAcceptanceError("required scratch indexes did not verify")
    created = await lifecycle.create_burn_in_run(
        operator, AUTHORITY, _key(database_name, "create"), plan,
        store=store, now=instant,
    )
    run = created["run"]
    provisioned = await provision_paused_burn_in_run(
        operator, AUTHORITY, run["run_id"], run["cursor"], run["sim_minute"],
        _key(database_name, "provision"), plan, store=store, now=instant,
    )
    run = provisioned["run"]
    resumed = await lifecycle.transition_run(
        operator, AUTHORITY, run["run_id"], lifecycle.PAUSED, lifecycle.RUNNING,
        run["cursor"], run["sim_minute"], _key(database_name, "resume-1"),
        plan, store=store, now=instant, require_unleased=True,
    )
    first = await _advance_and_tick(store, plan, resumed["run"], "first", instant)
    paused = await lifecycle.transition_run(
        operator, AUTHORITY, run["run_id"], lifecycle.RUNNING, lifecycle.PAUSED,
        first["run"]["cursor"], first["run"]["sim_minute"],
        _key(database_name, "pause"), plan, store=store, now=instant,
        require_unleased=True,
    )

    reopened = await _reopen(reopen_store)
    if getattr(reopened, "name", None) != database_name:
        raise CommunityMongoAcceptanceError("reopened store escaped the scratch database")
    persisted = await DatabaseRunnerTimeline(store=reopened, plan=plan).load_run(
        run_id=run["run_id"]
    )
    resumed_again = await lifecycle.transition_run(
        operator, AUTHORITY, run["run_id"], lifecycle.PAUSED, lifecycle.RUNNING,
        persisted["cursor"], persisted["sim_minute"], _key(database_name, "resume-2"),
        plan, store=reopened, now=instant, require_unleased=True,
    )
    second = await _advance_and_tick(
        reopened, plan, resumed_again["run"], "second", instant,
    )
    stopped = await lifecycle.transition_run(
        operator, AUTHORITY, run["run_id"], lifecycle.RUNNING, lifecycle.STOPPED,
        second["run"]["cursor"], second["run"]["sim_minute"],
        _key(database_name, "stop"), plan, store=reopened, now=instant,
        require_unleased=True,
    )
    reset = await reset_living_community(
        operator, AUTHORITY, _key(database_name, "reset"), run["run_id"],
        store=reopened, now=instant,
    )
    verification = await _verify_reset(reopened, reset)
    return {
        "status": "passed",
        "database": database_name,
        "probe": probe,
        "run_id": run["run_id"],
        "events_executed": [first["tick"].event_id, second["tick"].event_id],
        "restart_reloaded_state": persisted["state"],
        "final_run_state_before_reset": stopped["run"]["state"],
        "receipt_ids": {
            "indexes": indexes["receipt_id"],
            "create": created["receipt"]["receipt_id"],
            "provision": provisioned["receipt"]["receipt_id"],
            "first_event": first["tick"].receipt_id,
            "pause": paused["receipt"]["receipt_id"],
            "second_event": second["tick"].receipt_id,
            "stop": stopped["receipt"]["receipt_id"],
            "reset": reset["receipt_id"],
        },
        "reset": verification,
    }
