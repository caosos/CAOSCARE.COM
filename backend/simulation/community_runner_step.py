"""Execute exactly one already-validated canonical cursor event.

The runner owns plan validation and recovery checks.  This boundary preserves
the executor's lease, evidence, and cursor guarantees without rescanning the
entire immutable 90-day queue on every tick.
"""

from datetime import datetime
from typing import Callable, Optional

from simulation import community_executor as executor
from simulation import community_cursor_commit
from simulation import community_run_lease as run_lease
from simulation.community_blueprint import COMMUNITY_ID, SIMULATION_SCOPE


def _validate_event(event: executor.ExecutorEvent) -> None:
    if (
        not isinstance(event, executor.ExecutorEvent)
        or not event.event_id
        or event.actor_type != "simulated-agent"
        or event.identity_basis != "synthetic"
        or not event.simulated
        or not (
            event.actor_id.startswith("sim:staff:")
            or event.task_phase == "open" and event.actor_id == event.target_id
        )
    ):
        raise executor.CommunityExecutorError(
            "the cursor event lacks canonical synthetic actor provenance"
        )


async def execute_current(
    run_id: str,
    holder_id: str,
    fence: int,
    cursor: int,
    event: executor.ExecutorEvent,
    *,
    store,
    services: executor.ExecutorServices,
    now: datetime,
    ttl_seconds: int = run_lease.DEFAULT_TTL_SECONDS,
    clock: Optional[Callable[[], datetime]] = None,
    lease_mode: str = run_lease.RUNNER_MODE,
) -> executor.StepResult:
    """Execute/reconcile one supplied event under an exact fenced cursor."""
    _validate_event(event)
    context = executor.ExecutionContext(
        run_id=run_id,
        holder_id=holder_id,
        fence=fence,
        cursor=cursor,
        simulation_scope=SIMULATION_SCOPE,
        simulation_community_id=COMMUNITY_ID,
        lease_mode=lease_mode,
    )
    await executor._owned_run(store, context, now)
    evidence = await services.load_evidence(
        run_id=run_id,
        event_id=event.event_id,
        expected_cursor=cursor,
        execution_fence=fence,
    )
    replay = evidence is not None
    if evidence is None:
        await services.execute_event(event=event, context=context)
        evidence = await services.load_evidence(
            run_id=run_id,
            event_id=event.event_id,
            expected_cursor=cursor,
            execution_fence=fence,
        )
    proof = executor._validate_evidence(evidence, event, context)
    row = await community_cursor_commit.advance_cursor(
        run_id,
        holder_id,
        fence,
        cursor,
        store=store,
        clock=clock,
        ttl_seconds=ttl_seconds,
        lease_mode=lease_mode,
        fields={
            "last_event_id": event.event_id,
            "last_evidence_receipt_id": proof["receipt_id"],
            "last_evidence_status": proof["status"],
        },
    )
    return executor.StepResult(
        event_id=event.event_id,
        receipt_id=proof["receipt_id"],
        receipt_status=proof["status"],
        evidence_result=executor.RECEIPT_RESULTS[proof["status"]],
        cursor_before=cursor,
        cursor_after=row["cursor"],
        idempotent_replay=replay,
    )
