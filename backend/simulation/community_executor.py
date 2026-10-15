"""Fenced one-event core: no runner, route, DB default, or provider path."""
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable, Optional, Protocol
from simulation import community_cursor_commit, community_run_lease as run_lease
from simulation.community_blueprint import COMMUNITY_ID, SIMULATION_SCOPE
from simulation.community_ticket_plan import OPEN
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
    workflow_event_id: Optional[str] = None
    task_phase: Optional[str] = None
    # Capacity queue truth (routine tickets): when the resident asked, and on
    # the claim phase why and how long the ticket waited for a free worker.
    requested_at_minute: Optional[int] = None
    wait_reason: Optional[str] = None
    waited_minutes: Optional[int] = None
    # Minutes per blocker over the whole wait ((reason, minutes), ...), and
    # whether an off-site on-call worker was called in for this claim.
    wait_breakdown: Optional[tuple] = None
    called_in_on_call: bool = False
    # Who raised the ticket: the resident ("resident") or an on-site worker
    # ("staff"); on the OPEN phase actor_id is that person.
    opened_by: str = "resident"
@dataclass(frozen=True)
class ExecutionContext:
    run_id: str
    holder_id: str
    fence: int
    cursor: int
    simulation_scope: str
    simulation_community_id: str
    providers_allowed: bool = False
    lease_mode: str = run_lease.RUNNER_MODE
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
            or not (
                row.actor_id.startswith("sim:staff:")
                or row.task_phase == OPEN and row.actor_id == row.target_id
            )
        ):
            raise CommunityExecutorError("every executable event needs explicit synthetic actor provenance")
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
    if (
        not run_lease.owns_snapshot(
            row, context.holder_id, context.fence, instant,
            mode=context.lease_mode,
        )
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
    clock=None,
) -> StepResult:
    """Execute or reconcile exactly the event at the persisted cursor."""
    if services is None:
        raise CommunityExecutorError("execution services are required; no default provider path exists")
    if events is None:  # legacy single-day default; runtime passes the plan
        from simulation.community_day_queue import build_day_queue
        events = build_day_queue()
    queue = _validate_events(events)
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
    row = await community_cursor_commit.advance_cursor(
        run_id,
        holder_id,
        fence,
        cursor,
        store=store,
        clock=clock,
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
