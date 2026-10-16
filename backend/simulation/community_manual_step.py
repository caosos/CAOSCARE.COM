"""One owner-requested event under a durable PAUSED-run execution lease."""

from datetime import datetime, timezone
from hashlib import sha256
from typing import Callable, Optional

from routes.actor_context import ActorContext
from simulation import community_run_lease as lease
from simulation import community_run_lifecycle as lifecycle
from simulation import community_runner
from simulation.community_run_receipts import receipt_id, snapshot


REQUESTED = "simulation_community_manual_step_requested"
COMPLETED = "simulation_community_manual_step_completed"


class CommunityManualStepError(RuntimeError):
    """Manual step was refused without claiming successful execution."""


def _instant(value: Optional[datetime], clock: Callable[[], datetime]) -> datetime:
    instant = value or clock()
    if not isinstance(instant, datetime) or instant.tzinfo is None:
        raise CommunityManualStepError("manual step timestamps must be timezone-aware")
    return instant.astimezone(timezone.utc)


def _fresh(value: Optional[datetime], clock: Callable[[], datetime]) -> datetime:
    return _instant(None if value is None else value, clock)


def _key(parent: str, action: str) -> str:
    clean = (parent or "").strip()
    if not clean:
        raise CommunityManualStepError("a stable operation key is required")
    return f"manual-step:{action}:{sha256(clean.encode()).hexdigest()}"


def _receipt_identifier(run_id: str, operation_key: str) -> str:
    key_digest = sha256(_key(operation_key, "completed").encode()).hexdigest()
    return receipt_id(run_id, key_digest)


async def _replay(store, run_id, operation_key, operator, authority):
    prior = await store.receipts.find_one(
        {"_id": _receipt_identifier(run_id, operation_key)}, {"_id": 0},
    )
    if not prior:
        return None
    if (
        prior.get("action_type") != COMPLETED
        or prior.get("related_object_id") != run_id
        or prior.get("actor_id") != operator.actor_id
        or prior.get("authority") != authority
        or prior.get("status") != "completed"
    ):
        raise CommunityManualStepError("manual step replay evidence conflicts")
    row = await store.sim_runs.find_one({"run_id": run_id}, {"_id": 0})
    if not row or prior.get("after_state") != snapshot(row):
        raise CommunityManualStepError("manual step replay no longer matches run state")
    return {"run": row, "receipt": prior, "tick": None, "idempotent_replay": True}


async def execute_one(
    operator: ActorContext,
    authority: str,
    run_id: str,
    expected_cursor: int,
    expected_sim_minute: int,
    operation_key: str,
    holder_id: str,
    *,
    store,
    plan,
    timeline,
    services,
    ready,
    tick=community_runner.tick,
    now: Optional[datetime] = None,
    clock=lambda: datetime.now(timezone.utc),
) -> dict:
    """Keep PAUSED while one exact event reconciles/executes under a fence."""
    replay = await _replay(store, run_id, operation_key, operator, authority)
    if replay:
        return replay
    instant = _instant(now, clock)
    claim = await lease.acquire(
        run_id, holder_id, store=store, now=instant,
        mode=lease.MANUAL_STEP_MODE, expected_cursor=expected_cursor,
        expected_sim_minute=expected_sim_minute,
    )
    primary_error = None
    try:
        row = await timeline.load_run(run_id=run_id)
        if row.get("state") != lifecycle.PAUSED:
            raise CommunityManualStepError("manual step requires a PAUSED run")
        readiness = await ready(row)
        event = timeline.event_at(expected_cursor)
        if event is None:
            raise CommunityManualStepError("no event remains to step")
        await lifecycle._mutate(
            operator, authority, run_id, lifecycle.PAUSED, expected_cursor,
            expected_sim_minute, lifecycle.PAUSED, expected_sim_minute,
            _key(operation_key, "requested"), plan, REQUESTED,
            store=store, now=_fresh(now, clock), lease_claim=claim,
        )
        target_minute = event.day_index * 1440 + event.minute
        if target_minute > expected_sim_minute:
            lifecycle._runner_operator(
                lifecycle_actor(), f"simulation_run:{run_id}:clock", run_id, "clock",
            )
            await lifecycle._mutate(
                lifecycle_actor(), f"simulation_run:{run_id}:clock", run_id,
                lifecycle.PAUSED, expected_cursor, expected_sim_minute,
                lifecycle.PAUSED, target_minute, _key(operation_key, "clock"),
                plan, "simulation_community_manual_step_clock_advanced",
                store=store, now=_fresh(now, clock), human_operator=False,
                lease_claim=claim,
            )
        else:
            target_minute = expected_sim_minute
        result = await tick(
            run_id, holder_id, store=store, timeline=timeline,
            services=services, now=_fresh(now, clock), clock=clock,
            lease_mode=lease.MANUAL_STEP_MODE, claim=claim,
            release_claim=False,
        )
        delta = result.cursor_after - result.cursor_before
        if (
            result.run_id != run_id
            or result.cursor_before != expected_cursor
            or delta not in (0, 1)
            or result.status not in {"executed", "advanced", "blocked"}
            or (delta == 1 and not result.receipt_id)
            or (delta == 0 and result.status != "blocked")
        ):
            raise CommunityManualStepError(
                "step result does not prove one exact event attempt"
            )
        completed = await lifecycle._mutate(
            operator, authority, run_id, lifecycle.PAUSED, result.cursor_after,
            target_minute, lifecycle.PAUSED, target_minute,
            _key(operation_key, "completed"), plan, COMPLETED,
            store=store, now=_fresh(now, clock),
            lease_claim=claim,
        )
        return {
            **completed, "tick": result, "readiness": readiness,
            "idempotent_replay": completed["idempotent_replay"],
        }
    except BaseException as exc:
        primary_error = exc
        raise
    finally:
        try:
            await lease.release(
                run_id, holder_id, claim["fence"], store=store,
                now=_fresh(now, clock),
            )
        except lease.RunLeaseError:
            if primary_error is None:
                raise


def lifecycle_actor() -> ActorContext:
    return ActorContext(
        actor_id=lifecycle.CLOCK_ACTOR_ID,
        actor_type="system",
        identity_basis="system",
        channel="system",
        name="Living Community Runner",
        role="system",
        simulated=False,
    )
