"""Atomic lifecycle boundary for one living-community burn-in run.

No route, loop, provider, resident writer, or default store: every accepted
mutation and its receipt commit through injected transactional storage.
"""
from datetime import datetime, timezone
from functools import lru_cache
from hashlib import sha256
from typing import Optional

from pymongo import ReturnDocument

from routes.actor_context import ActorContext
from simulation.community_blueprint import COMMUNITY_ID, SIMULATION_SCOPE
from simulation.community_provisioning import ProvisioningError, _require_operator
from simulation import community_run_lease as run_lease
from simulation.community_run_receipts import build_receipt, receipt_id, snapshot
from simulation.community_timeline import CommunityTimeline, validate_timeline

PAUSED = "PAUSED"
RUNNING = "RUNNING"
STOPPED = "STOPPED"
RUN_KIND = "living_community_burn_in"
CLOCK_ACTOR_ID = "system:living-community-runner"

class CommunityRunLifecycleError(RuntimeError):
    """A lifecycle request was refused without committing state or evidence."""


def _utc(value: Optional[datetime]) -> datetime:
    instant = value or datetime.now(timezone.utc)
    if instant.tzinfo is None:
        raise CommunityRunLifecycleError("lifecycle timestamps must be timezone-aware")
    return instant.astimezone(timezone.utc)


def _operator(operator: ActorContext, authority: str) -> None:
    try:
        _require_operator(operator, authority)
    except ProvisioningError as exc:
        raise CommunityRunLifecycleError(str(exc)) from exc


def _runner_operator(
    operator: ActorContext, authority: str, run_id: str, capability: str,
) -> None:
    if (
        operator.actor_id != CLOCK_ACTOR_ID
        or operator.actor_type != "system"
        or operator.identity_basis != "system"
        or operator.channel != "system"
        or operator.simulated
        or authority != f"simulation_run:{run_id}:{capability}"
    ):
        raise CommunityRunLifecycleError(
            f"{capability} requires the named runner and run-scoped authority"
        )


def _key(value: str) -> tuple[str, str]:
    clean = (value or "").strip()
    if not clean or len(clean) > 160:
        raise CommunityRunLifecycleError("a stable idempotency key of 1-160 characters is required")
    return clean, sha256(clean.encode()).hexdigest()


@lru_cache(maxsize=4)
def _plan(plan: CommunityTimeline) -> dict:
    try:
        checked = validate_timeline(plan)
    except (TypeError, ValueError) as exc:
        raise CommunityRunLifecycleError("the canonical timeline revision or digest is invalid") from exc
    return {
        "plan_revision": checked.plan_revision,
        "plan_digest_sha256": checked.digest_sha256,
        "event_count": checked.event_count,
        "timeline_days": checked.day_count,
        "timeline_end_minute": checked.day_count * 1440 - 1,
    }


def _scope(run_id: str) -> dict:
    return {
        "run_id": run_id,
        "simulation_scope": SIMULATION_SCOPE,
        "simulation_community_id": COMMUNITY_ID,
        "run_kind": RUN_KIND,
    }


async def _candidates(store, run_id: str, session) -> list[dict]:
    cursor = store.sim_runs.find({"$or": [
        {"run_id": run_id},
        {"simulation_scope": SIMULATION_SCOPE},
        {"simulation_community_id": COMMUNITY_ID},
    ]}, {"_id": 0}, session=session)
    return await cursor.to_list(None)


async def _one_run(store, run_id: str, session) -> dict:
    rows = await _candidates(store, run_id, session)
    if len(rows) != 1 or any(any(row.get(k) != v for k, v in _scope(run_id).items()) for row in rows):
        raise CommunityRunLifecycleError("run scope is missing, ambiguous, or conflicts with another run")
    return rows[0]


def _same_plan(row: dict, fields: dict) -> bool:
    return all(row.get(key) == value for key, value in fields.items())


async def _prior(store, receipt_id: str, session) -> Optional[dict]:
    return await store.receipts.find_one({"_id": receipt_id}, {"_id": 0}, session=session)


def _replay(prior: dict, row: dict, action: str) -> dict:
    if (
        prior.get("action_type") != action
        or prior.get("after_state") != snapshot(row)
        or row.get("last_transition_receipt_id") != prior.get("receipt_id")
    ):
        raise CommunityRunLifecycleError("idempotency key conflicts with changed or different lifecycle state")
    return {"run": row, "receipt": prior, "idempotent_replay": True}


async def create_burn_in_run(
    operator: ActorContext, authority: str, idempotency_key: str,
    plan: CommunityTimeline, *, store, now: Optional[datetime] = None,
) -> dict:
    """Create one PAUSED, unprovisioned ten-resident burn-in run."""
    _operator(operator, authority)
    _, digest = _key(idempotency_key)
    fields, instant = _plan(plan), _utc(now)
    run_id = f"simrun:living:{sha256(f'{COMMUNITY_ID}:{digest}'.encode()).hexdigest()[:20]}"
    receipt_id_value = receipt_id(run_id, digest)
    client = getattr(store, "client", None)
    if client is None or not callable(getattr(client, "start_session", None)):
        raise CommunityRunLifecycleError("transaction-capable injected storage is required")
    async with await client.start_session() as session:
        async with session.start_transaction():
            rows = await _candidates(store, run_id, session)
            if rows:
                row = await _one_run(store, run_id, session)
                prior = await _prior(store, receipt_id_value, session)
                if not prior or not _same_plan(row, fields) or row.get("creation_key_sha256") != digest:
                    raise CommunityRunLifecycleError("an existing run conflicts with this creation request")
                return _replay(prior, row, "simulation_community_run_created")
            row = {
                "_id": run_id, **_scope(run_id), **fields, "state": PAUSED,
                "cursor": 0, "sim_minute": 0, "cohort": plan.cohort, "resident_count": plan.resident_count,
                "residents_provisioned": False, "creation_key_sha256": digest,
                "created_by": operator.receipt_fields(), "original_human_starter": None,
                "origin_receipt_id": receipt_id_value,
                "last_transition_receipt_id": receipt_id_value,
                "created_at": instant.isoformat(), "updated_at": instant.isoformat(),
                "sim_clock_at": instant.isoformat(),
            }
            receipt = build_receipt(
                "simulation_community_run_created", receipt_id_value, digest, row,
                operator, authority, instant, None, snapshot(row),
            )
            await store.sim_runs.insert_one(dict(row), session=session)
            await store.receipts.insert_one(receipt, session=session)
            row.pop("_id", None)
            receipt.pop("_id", None)
            return {"run": row, "receipt": receipt, "idempotent_replay": False}


async def _mutate(
    operator, authority, run_id, expected_state, expected_cursor,
    expected_sim_minute, next_state, next_minute, operation_key, plan,
    action, *, store, now, human_operator=True, require_unleased=False,
    lease_claim=None,
) -> dict:
    if human_operator:
        _operator(operator, authority)
    if any(not isinstance(value, int) or isinstance(value, bool) or value < 0
           for value in (expected_cursor, expected_sim_minute, next_minute)):
        raise CommunityRunLifecycleError("cursor and simulated clock coordinates must be non-negative integers")
    _, digest = _key(operation_key)
    fields, instant = _plan(plan), _utc(now)
    if require_unleased and lease_claim is not None:
        raise CommunityRunLifecycleError("a mutation cannot require both an absent and owned lease")
    receipt_id_value = receipt_id(run_id, digest)
    client = getattr(store, "client", None)
    if client is None or not callable(getattr(client, "start_session", None)):
        raise CommunityRunLifecycleError("transaction-capable injected storage is required")
    async with await client.start_session() as session:
        async with session.start_transaction():
            row = await _one_run(store, run_id, session)
            prior = await _prior(store, receipt_id_value, session)
            if prior:
                return _replay(prior, row, action)
            if not _same_plan(row, fields):
                raise CommunityRunLifecycleError("persisted run plan revision or digest is invalid")
            query = {
                **_scope(run_id), **fields, "state": expected_state,
                "cursor": expected_cursor, "sim_minute": expected_sim_minute,
            }
            if require_unleased:
                query["execution_lease"] = {"$exists": False}
            if lease_claim is not None:
                try:
                    query.update(run_lease.ownership_fields(
                        lease_claim["holder_id"], lease_claim["fence"], instant,
                        mode=lease_claim["mode"],
                    ))
                except (KeyError, run_lease.RunLeaseError) as exc:
                    raise CommunityRunLifecycleError("exact execution lease proof is invalid") from exc
            updates = {
                "state": next_state, "sim_minute": next_minute,
                "last_transition_receipt_id": receipt_id_value,
                "updated_at": instant.isoformat(),
                # Real time at which sim_minute was last set; the accelerated
                # clock measures from here (lease writes also touch updated_at).
                "sim_clock_at": instant.isoformat(),
            }
            if action == "simulation_community_run_resumed" and not row.get("original_human_starter"):
                updates["original_human_starter"] = operator.receipt_fields()
            if action == "simulation_community_run_completed":
                updates.update(
                    terminal_reason="completed", completed_at=instant.isoformat(),
                    completion_receipt_id=receipt_id_value,
                )
            update = {"$set": updates}
            if next_state in (PAUSED, STOPPED) and next_state != expected_state:
                update["$unset"] = {"execution_lease": ""}
            changed = await store.sim_runs.find_one_and_update(
                query, update, projection={"_id": 0}, session=session,
                return_document=ReturnDocument.AFTER,
            )
            if not changed:
                raise CommunityRunLifecycleError("stale state, cursor, clock, scope, or plan refused")
            receipt = build_receipt(
                action, receipt_id_value, digest, row, operator, authority, instant,
                snapshot(row), snapshot(changed),
            )
            await store.receipts.insert_one(receipt, session=session)
            receipt.pop("_id", None)
            return {"run": changed, "receipt": receipt, "idempotent_replay": False}


async def transition_run(
    operator: ActorContext, authority: str, run_id: str, expected_state: str,
    next_state: str, expected_cursor: int, expected_sim_minute: int,
    operation_key: str, plan: CommunityTimeline, *, store,
    now: Optional[datetime] = None, require_unleased: bool = False,
) -> dict:
    allowed = {(PAUSED, RUNNING), (RUNNING, PAUSED), (PAUSED, STOPPED), (RUNNING, STOPPED)}
    if (expected_state, next_state) not in allowed:
        raise CommunityRunLifecycleError("invalid run lifecycle transition")
    action = {
        (PAUSED, RUNNING): "simulation_community_run_resumed",
        (RUNNING, PAUSED): "simulation_community_run_paused",
        (PAUSED, STOPPED): "simulation_community_run_stopped",
        (RUNNING, STOPPED): "simulation_community_run_stopped",
    }[(expected_state, next_state)]
    return await _mutate(
        operator, authority, run_id, expected_state, expected_cursor,
        expected_sim_minute, next_state, expected_sim_minute, operation_key,
        plan, action, store=store, now=now, require_unleased=require_unleased,
    )


async def advance_simulated_clock(
    operator: ActorContext, authority: str, run_id: str, expected_cursor: int,
    expected_sim_minute: int, next_sim_minute: int, operation_key: str,
    plan: CommunityTimeline, *, store, now: Optional[datetime] = None,
) -> dict:
    _runner_operator(operator, authority, run_id, "clock")
    fields = _plan(plan)
    if next_sim_minute <= expected_sim_minute or next_sim_minute > fields["timeline_end_minute"]:
        raise CommunityRunLifecycleError("simulated clock must advance monotonically within the timeline")
    return await _mutate(
        operator, authority, run_id, RUNNING, expected_cursor,
        expected_sim_minute, RUNNING, next_sim_minute, operation_key, plan,
        "simulation_community_clock_advanced", store=store, now=now,
        human_operator=False, require_unleased=True,
    )


async def complete_run(
    operator: ActorContext, authority: str, run_id: str, expected_cursor: int,
    expected_sim_minute: int, operation_key: str, plan: CommunityTimeline,
    *, store, now: Optional[datetime] = None,
) -> dict:
    """Atomically stop a fully executed plan at the exact 90-day boundary."""
    _runner_operator(operator, authority, run_id, "complete")
    fields = _plan(plan)
    if expected_cursor != fields["event_count"]:
        raise CommunityRunLifecycleError("completion requires every planned event")
    if expected_sim_minute > fields["timeline_end_minute"]:
        raise CommunityRunLifecycleError("completion clock is beyond the active timeline")
    return await _mutate(
        operator, authority, run_id, RUNNING, expected_cursor,
        expected_sim_minute, STOPPED, fields["timeline_end_minute"] + 1,
        operation_key, plan, "simulation_community_run_completed",
        store=store, now=now, human_operator=False, require_unleased=True,
    )
