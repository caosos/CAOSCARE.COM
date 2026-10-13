"""One fenced simulator tick with injected storage and service boundaries.

This module deliberately supplies no loop, startup hook, route, provider, or
default database.  A caller may request one tick; the tick may reconcile or
execute at most the event at the persisted cursor.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, Iterable, Optional, Protocol

from simulation import community_executor as executor
from simulation import community_run_lease as run_lease
from simulation.community_blueprint import COMMUNITY_ID, SIMULATION_SCOPE
from simulation.community_reconciliation import reconcile_run


class CommunityRunnerError(RuntimeError):
    """A tick was refused without executing new community work."""


class RunnerTimeline(Protocol):
    """Injected durable timeline reads used for restart reconciliation."""

    async def load_run(self, *, run_id: str) -> dict: ...

    async def load_events(
        self, *, run_id: str
    ) -> Iterable[executor.ExecutorEvent]: ...

    async def load_receipts(self, *, run_id: str) -> Iterable[dict]: ...


@dataclass(frozen=True)
class TickResult:
    run_id: str
    status: str
    action: str
    event_id: Optional[str]
    receipt_id: Optional[str]
    cursor_before: int
    cursor_after: int
    fence: int
    idempotent_replay: bool


def _utc(value: Optional[datetime]) -> datetime:
    instant = value or datetime.now(timezone.utc)
    if instant.tzinfo is None:
        raise CommunityRunnerError("runner timestamps must be timezone-aware")
    return instant.astimezone(timezone.utc)


def _no_action(run_id: str, plan: dict, fence: int) -> TickResult:
    cursor = plan["cursor"]
    if plan["status"] == "paused":
        status = "paused"
    elif plan["status"] == "terminal":
        status = "stopped" if plan["run_state"] == "STOPPED" else "complete"
    else:
        rows = plan["classified_events"]
        status = rows[cursor]["classification"] if cursor < len(rows) else "complete"
    return TickResult(run_id, status, "none", None, None, cursor, cursor, fence, False)


def _explicitly_blocked(event) -> bool:
    if isinstance(event, dict):
        return bool(
            event.get("blocked") is True
            or event.get("blocked_capability")
            or event.get("execution_state") == "blocked"
            or event.get("adapter_status") == "blocked"
        )
    return bool(getattr(event, "blocked_capability", None))


def _recovery_receipt(receipts: tuple[dict, ...], step: dict) -> dict:
    matches = [row for row in receipts if row.get("receipt_id") == step["receipt_id"]]
    if len(matches) != 1:
        raise CommunityRunnerError("recovery receipt is missing or ambiguous")
    return matches[0]


def _validate_recovery_proof(
    proof: dict,
    event: executor.ExecutorEvent,
    *,
    run_id: str,
    holder_id: str,
    cursor: int,
) -> dict:
    old_fence = proof.get("execution_fence")
    if not isinstance(old_fence, int) or isinstance(old_fence, bool) or old_fence < 1:
        raise CommunityRunnerError("recovery receipt has no valid execution fence")
    context = executor.ExecutionContext(
        run_id=run_id,
        holder_id=holder_id,
        fence=old_fence,
        cursor=cursor,
        simulation_scope=SIMULATION_SCOPE,
        simulation_community_id=COMMUNITY_ID,
    )
    try:
        return executor._validate_evidence(proof, event, context)
    except executor.CommunityExecutorError as exc:
        raise CommunityRunnerError("recovery receipt failed provenance validation") from exc


async def tick(
    run_id: str,
    holder_id: str,
    *,
    store,
    timeline: RunnerTimeline,
    services: executor.ExecutorServices,
    now: Optional[datetime] = None,
    ttl_seconds: int = run_lease.DEFAULT_TTL_SECONDS,
    clock: Optional[Callable[[], datetime]] = None,
) -> TickResult:
    """Acquire, reconcile, and process no more than one cursor event."""
    instant = _utc(now)
    claim = None
    primary_error = None
    try:
        claim = await run_lease.acquire(
            run_id, holder_id, store=store, now=instant, ttl_seconds=ttl_seconds
        )
        events = tuple(await timeline.load_events(run_id=run_id))
        receipts = tuple(await timeline.load_receipts(run_id=run_id))
        run = await timeline.load_run(run_id=run_id)
        plan = reconcile_run(run, events, receipts, max_recovery_events=1)

        if plan["run_state"] == run_lease.PAUSED:
            return _no_action(run_id, plan, claim["fence"])

        # A state/fence change after the snapshot must stop the tick before it
        # reports or performs work.
        owned = await run_lease.heartbeat(
            run_id,
            holder_id,
            claim["fence"],
            store=store,
            now=instant,
            ttl_seconds=ttl_seconds,
        )
        if (
            owned.get("cursor") != plan["cursor"]
            or owned.get("sim_minute") != plan["sim_minute"]
        ):
            raise CommunityRunnerError("timeline snapshot is stale")
        if plan["status"] == "inconsistent":
            raise CommunityRunnerError("timeline reconciliation is inconsistent")
        cursor = plan["cursor"]
        if cursor < len(events) and _explicitly_blocked(events[cursor]):
            return TickResult(
                run_id, "blocked", "none", None, None,
                cursor, cursor, claim["fence"], False,
            )
        if not plan["recovery_steps"]:
            return _no_action(run_id, plan, claim["fence"])

        step = plan["recovery_steps"][0]
        if step["expected_cursor"] != cursor or cursor >= len(events):
            raise CommunityRunnerError("recovery step does not match the persisted cursor")
        event = events[cursor]
        if step["event_id"] != event.event_id:
            raise CommunityRunnerError("recovery event does not match the deterministic stream")

        if step["action"] == "advance_cursor_from_receipt":
            proof = _validate_recovery_proof(
                _recovery_receipt(receipts, step),
                event,
                run_id=run_id,
                holder_id=holder_id,
                cursor=cursor,
            )
            fresh = _utc(clock() if clock else None)
            await run_lease.heartbeat(
                run_id,
                holder_id,
                claim["fence"],
                store=store,
                now=fresh,
                ttl_seconds=ttl_seconds,
            )
            row = await run_lease.advance_cursor(
                run_id,
                holder_id,
                claim["fence"],
                cursor,
                cursor + 1,
                store=store,
                now=fresh,
                fields={
                    "last_event_id": event.event_id,
                    "last_evidence_receipt_id": proof["receipt_id"],
                    "last_evidence_status": proof["status"],
                },
            )
            return TickResult(
                run_id, "advanced", step["action"], event.event_id,
                proof["receipt_id"], cursor, row["cursor"], claim["fence"], True,
            )

        if step["action"] != "execute_event_then_advance":
            raise CommunityRunnerError("unknown recovery action")
        result = await executor.execute_one(
            run_id,
            holder_id,
            claim["fence"],
            store=store,
            services=services,
            events=events,
            now=instant,
            clock=clock,
        )
        return TickResult(
            run_id, "executed", step["action"], result.event_id,
            result.receipt_id, result.cursor_before, result.cursor_after,
            claim["fence"], result.idempotent_replay,
        )
    except BaseException as exc:
        primary_error = exc
        raise
    finally:
        if claim is not None:
            try:
                await run_lease.release(
                    run_id, holder_id, claim["fence"], store=store, now=instant
                )
            except run_lease.RunLeaseError:
                if primary_error is None:
                    raise
