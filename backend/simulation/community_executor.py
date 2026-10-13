"""Fenced one-event core: no runner, route, DB default, or provider path."""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable, Optional, Protocol

from simulation import community_run_lease as run_lease
from simulation.community_blueprint import BURN_IN_RESIDENTS, COMMUNITY_ID, SIMULATION_SCOPE
from simulation.community_dispatch import plan_routine_dispatch
from simulation.community_routines import RoutineEvent, plan_first_24_hours
from simulation.community_shift_events import planned_events_for_day
from simulation.community_staffing import active_assignments


RECEIPT_RESULTS = {
    "completed": "succeeded",
    "failed": "observed",
    "cancelled": "refused",
}


class CommunityExecutorError(RuntimeError):
    """One event was refused without advancing the cursor."""

@dataclass(frozen=True)
class ExecutorEvent:
    event_id: str
    stream_kind: str
    action_type: str
    day_index: int
    minute: int
    actor_id: str
    actor_name: str
    actor_type: str
    identity_basis: str
    department: str
    target_type: str
    target_id: str
    adapter: str
    simulated: bool = True
    blocked_capability: Optional[str] = None

@dataclass(frozen=True)
class ExecutionContext:
    run_id: str
    holder_id: str
    fence: int
    cursor: int
    simulation_scope: str
    simulation_community_id: str
    providers_allowed: bool = False


@dataclass(frozen=True)
class StepResult:
    event_id: str
    receipt_id: str
    receipt_status: str
    evidence_result: str
    cursor_before: int
    cursor_after: int
    idempotent_replay: bool


class ExecutorServices(Protocol):
    """Injected boundary; load_evidence reads a persisted canonical receipt."""

    async def load_evidence(self, *, run_id: str, event_id: str,
                            expected_cursor: int, execution_fence: int) -> Optional[dict]: ...

    async def execute_event(self, *, event: ExecutorEvent,
                            context: ExecutionContext) -> object: ...


def _routine_event(event: RoutineEvent, ready_day: int, ready_minute: int) -> ExecutorEvent:
    workers = sorted(
        (
            row
            for row in active_assignments(ready_day, ready_minute)
            if row["department"] == event.department
        ),
        key=lambda row: row["actor_id"],
    )
    if not workers:
        raise CommunityExecutorError(f"dispatch has no on-shift actor: {event.event_id}")
    actor = workers[0]
    resident = next(
        (row for row in BURN_IN_RESIDENTS if row.resident_key == event.resident_key),
        None,
    )
    if resident is None:
        raise CommunityExecutorError(f"event is outside the burn-in residents: {event.event_id}")
    return ExecutorEvent(
        event_id=event.event_id,
        stream_kind="routine_dispatch",
        action_type=event.routine,
        day_index=ready_day,
        minute=ready_minute,
        actor_id=actor["actor_id"],
        actor_name=actor["name"],
        actor_type=actor["actor_type"],
        identity_basis=actor["identity_basis"],
        department=event.department,
        target_type="resident",
        target_id=resident.resident_id,
        adapter=event.adapter,
        blocked_capability=event.blocked_adapter,
    )


def build_day_queue(day_index: int = 0) -> tuple[ExecutorEvent, ...]:
    """Combine canonical shift milestones and coverage-gated routine intents."""
    routines = plan_first_24_hours(day_index=day_index)
    dispatch = {row.event_id: row for row in plan_routine_dispatch(routines)}
    events = [
        _routine_event(
            event,
            dispatch[event.event_id].ready_day_index,
            dispatch[event.event_id].ready_minute,
        )
        for event in routines
    ]
    for event in planned_events_for_day(day_index):
        if event["stream_kind"] != "canonical_shift_milestone":
            continue
        events.append(ExecutorEvent(
            event_id=event["event_id"],
            stream_kind=event["stream_kind"],
            action_type=event["event_type"],
            day_index=event["day_index"],
            minute=event["minute"],
            actor_id=event["actor_id"],
            actor_name=event["actor_name"],
            actor_type=event["actor_type"],
            identity_basis=event["identity_basis"],
            department=event["department"],
            target_type=event["target_type"],
            target_id=event["target_id"],
            adapter="canonical_shift_service",
            simulated=event["actor_simulated"],
        ))
    return tuple(sorted(events, key=lambda row: (
        row.day_index * 1440 + row.minute, row.stream_kind, row.event_id,
    )))


def _utc(value: Optional[datetime]) -> datetime:
    instant = value or datetime.now(timezone.utc)
    if instant.tzinfo is None:
        raise CommunityExecutorError("executor timestamps must be timezone-aware")
    return instant.astimezone(timezone.utc)


def _validate_events(events: Iterable[ExecutorEvent]) -> tuple[ExecutorEvent, ...]:
    rows = tuple(events)
    if not rows or len({row.event_id for row in rows}) != len(rows):
        raise CommunityExecutorError("event queue must be non-empty with unique ids")
    for row in rows:
        if (
            not row.event_id
            or row.actor_type != "simulated-agent"
            or row.identity_basis != "synthetic"
            or not row.simulated
            or not row.actor_id.startswith("sim:staff:")
        ):
            raise CommunityExecutorError("every executable event needs explicit synthetic staff provenance")
    return rows


def _validate_evidence(
    evidence: Optional[dict], event: ExecutorEvent, context: ExecutionContext
) -> dict:
    if not evidence:
        raise CommunityExecutorError("canonical service produced no durable evidence")
    required = {key: evidence.get(key) for key in (
        "receipt_id", "simulation_event_id", "simulation_run_id", "actor_id", "status",
    )}
    evidence_fence = evidence.get("execution_fence")
    if any(not value for value in required.values()):
        raise CommunityExecutorError("canonical receipt evidence is incomplete")
    if (
        evidence["simulation_event_id"] != event.event_id
        or evidence["simulation_run_id"] != context.run_id
        or evidence.get("simulation_scope") != SIMULATION_SCOPE
        or evidence.get("simulation_community_id") != COMMUNITY_ID
        or evidence.get("execution_cursor") != context.cursor
        or not isinstance(evidence_fence, int)
        or isinstance(evidence_fence, bool)
        or evidence_fence != context.fence
        or evidence["actor_id"] != event.actor_id
        or evidence.get("actor_type") != "simulated-agent"
        or evidence.get("identity_basis") != "synthetic"
        or evidence.get("simulated") is not True
        or evidence.get("channel") != "simulator"
        or evidence.get("authority") != "living_community_executor"
        or evidence.get("action_type") != event.action_type
        or evidence.get("related_object_type") != event.target_type
        or evidence.get("related_object_id") != event.target_id
        or evidence["status"] not in RECEIPT_RESULTS
    ):
        raise CommunityExecutorError("durable evidence does not match this event and provenance")
    return evidence


async def _owned_run(store, context: ExecutionContext, instant: datetime) -> dict:
    row = await store.sim_runs.find_one({
        "run_id": context.run_id,
        "simulation_scope": SIMULATION_SCOPE,
        "simulation_community_id": COMMUNITY_ID,
    }, {"_id": 0})
    lease = (row or {}).get("execution_lease") or {}
    expires_at = lease.get("expires_at")
    try:
        expires = datetime.fromisoformat(expires_at) if expires_at else None
    except (TypeError, ValueError):
        expires = None
    if (
        not row
        or row.get("state") != run_lease.RUNNING
        or row.get("execution_lease_generation") != context.fence
        or lease.get("holder_id") != context.holder_id
        or not expires
        or expires.tzinfo is None
        or expires.astimezone(timezone.utc) <= instant
    ):
        raise CommunityExecutorError("run is paused or lease ownership is stale or expired")
    if row.get("cursor") != context.cursor:
        raise CommunityExecutorError("persisted cursor does not match the requested step")
    return row


async def execute_one(
    run_id: str,
    holder_id: str,
    fence: int,
    *,
    store,
    services: Optional[ExecutorServices] = None,
    events: Optional[Iterable[ExecutorEvent]] = None,
    now: Optional[datetime] = None,
) -> StepResult:
    """Execute or reconcile exactly the event at the persisted cursor."""
    if services is None:
        raise CommunityExecutorError("execution services are required; no default provider path exists")
    queue = _validate_events(build_day_queue() if events is None else events)
    instant = _utc(now)
    initial = await store.sim_runs.find_one({
        "run_id": run_id,
        "simulation_scope": SIMULATION_SCOPE,
        "simulation_community_id": COMMUNITY_ID,
    }, {"_id": 0})
    cursor = (initial or {}).get("cursor")
    if not isinstance(cursor, int) or isinstance(cursor, bool) or not 0 <= cursor < len(queue):
        raise CommunityExecutorError("persisted cursor is missing or outside the event queue")
    context = ExecutionContext(
        run_id=run_id,
        holder_id=holder_id,
        fence=fence,
        cursor=cursor,
        simulation_scope=SIMULATION_SCOPE,
        simulation_community_id=COMMUNITY_ID,
    )
    await _owned_run(store, context, instant)
    event = queue[cursor]
    evidence = await services.load_evidence(
        run_id=run_id, event_id=event.event_id, expected_cursor=cursor,
        execution_fence=fence,
    )
    replay = evidence is not None
    if evidence is None:
        await services.execute_event(event=event, context=context)
        evidence = await services.load_evidence(
            run_id=run_id, event_id=event.event_id, expected_cursor=cursor,
            execution_fence=fence,
        )
    proof = _validate_evidence(evidence, event, context)
    row = await run_lease.advance_cursor(
        run_id,
        holder_id,
        fence,
        cursor,
        cursor + 1,
        store=store,
        now=instant,
        fields={
            "last_event_id": event.event_id,
            "last_evidence_receipt_id": proof["receipt_id"],
            "last_evidence_status": proof["status"],
        },
    )
    return StepResult(
        event_id=event.event_id,
        receipt_id=proof["receipt_id"],
        receipt_status=proof["status"],
        evidence_result=RECEIPT_RESULTS[proof["status"]],
        cursor_before=cursor,
        cursor_after=row["cursor"],
        idempotent_replay=replay,
    )
