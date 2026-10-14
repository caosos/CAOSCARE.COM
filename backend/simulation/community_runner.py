"""One fenced simulator tick with injected storage and service boundaries.

This module deliberately supplies no loop, startup hook, route, provider, or
default database.  A caller may request one tick; the tick may reconcile or
execute at most the event at the persisted cursor.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, Optional, Protocol

from simulation import community_executor as executor
from simulation import community_cursor_commit
from simulation import community_run_lease as run_lease
from simulation import community_runner_step
from simulation.community_blueprint import COMMUNITY_ID, SIMULATION_SCOPE
from simulation.community_routines import ADAPTER_CAPABILITIES, BLOCKED


class CommunityRunnerError(RuntimeError):
    """A tick was refused without executing new community work."""


class RunnerTimeline(Protocol):
    """Injected cursor-local timeline reads used for restart recovery."""

    event_count: int

    async def load_run(self, *, run_id: str) -> dict: ...

    def event_at(self, cursor: int) -> Optional[executor.ExecutorEvent]: ...

    async def load_bounded_evidence(
        self, *, run_id: str, cursor: int, event_id: Optional[str],
        last_event_id: Optional[str], last_receipt_id: Optional[str],
    ) -> dict: ...


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


def _no_action(run_id: str, status: str, cursor: int, fence: int) -> TickResult:
    return TickResult(
        run_id, status, "none", None, None, cursor, cursor, fence, False,
    )


def _explicitly_blocked(event) -> bool:
    if isinstance(event, dict):
        return bool(
            event.get("blocked") is True
            or event.get("blocked_capability")
            or event.get("execution_state") == "blocked"
            or event.get("adapter_status") == "blocked"
        )
    # ``blocked_capability`` names a capability the ticket deliberately does
    # not invoke (its receipt records ``blocked_capability_not_invoked``); the
    # event itself runs through its safe canonical adapter.  Only an event
    # whose own adapter is blocked must never execute.
    return ADAPTER_CAPABILITIES.get(getattr(event, "adapter", None), {}).get("status") == BLOCKED


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


def _coordinate(value, label: str, maximum: Optional[int] = None) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise CommunityRunnerError(f"{label} must be a non-negative integer")
    if maximum is not None and value > maximum:
        raise CommunityRunnerError(f"{label} exceeds the canonical plan")
    return value


def _event_minute(event: executor.ExecutorEvent) -> int:
    day = _coordinate(event.day_index, "event day")
    minute = _coordinate(event.minute, "event minute", 1439)
    return day * 1440 + minute


def _inconsistent(reason: str) -> CommunityRunnerError:
    return CommunityRunnerError(f"timeline reconciliation is inconsistent: {reason}")


def _validate_last_evidence(
    run: dict, timeline: RunnerTimeline, window: dict, *, run_id: str,
    holder_id: str, cursor: int,
) -> None:
    fields = (
        run.get("last_event_id"), run.get("last_evidence_receipt_id"),
        run.get("last_evidence_status"),
    )
    if cursor == 0:
        if any(value is not None for value in fields) or window["previous"]:
            raise _inconsistent("cursor zero cannot claim last-event evidence")
        return
    previous_event = timeline.event_at(cursor - 1)
    if previous_event is None or run.get("last_event_id") != previous_event.event_id:
        raise _inconsistent("last_event_id does not match the persisted cursor")
    if len(window["previous"]) != 1:
        raise _inconsistent("last evidence receipt is missing or ambiguous")
    proof = _validate_recovery_proof(
        window["previous"][0], previous_event, run_id=run_id,
        holder_id=holder_id, cursor=cursor - 1,
    )
    if (
        proof["receipt_id"] != run.get("last_evidence_receipt_id")
        or proof["status"] != run.get("last_evidence_status")
    ):
        raise _inconsistent("persisted last evidence fields do not match the receipt")


def _current_proof(
    run: dict, event: Optional[executor.ExecutorEvent], window: dict, *,
    run_id: str, holder_id: str, cursor: int,
) -> Optional[dict]:
    if window["future"]:
        raise _inconsistent("receipt exists after an unresolved cursor gap")
    rows = tuple(window["current"])
    if len(rows) > 1:
        raise _inconsistent("multiple receipts ambiguously reference the cursor event")
    if not rows:
        return None
    if event is None:
        raise _inconsistent("receipt exists beyond the terminal cursor")
    try:
        proof = _validate_recovery_proof(
            rows[0], event, run_id=run_id, holder_id=holder_id, cursor=cursor,
        )
    except CommunityRunnerError as exc:
        raise _inconsistent(str(exc)) from exc
    if _event_minute(event) > run["sim_minute"]:
        raise _inconsistent("cursor event has a receipt later than simulated time")
    return proof


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
    lease_mode: str = run_lease.RUNNER_MODE,
    claim: Optional[dict] = None,
    release_claim: bool = True,
) -> TickResult:
    """Acquire, reconcile, and process no more than one cursor event."""
    instant = _utc(now)
    supplied_claim = claim is not None
    primary_error = None
    try:
        if claim is None:
            claim = await run_lease.acquire(
                run_id, holder_id, store=store, now=instant,
                ttl_seconds=ttl_seconds, mode=lease_mode,
            )
        if not run_lease.claim_matches(claim, run_id, holder_id, lease_mode):
            raise CommunityRunnerError("supplied lease claim does not match this tick")
        run = await timeline.load_run(run_id=run_id)
        cursor = _coordinate(run.get("cursor"), "run cursor", timeline.event_count)
        _coordinate(run.get("sim_minute"), "run simulated minute")
        if run.get("state") not in run_lease.ACTIVE:
            raise CommunityRunnerError("run state is not active")
        event = timeline.event_at(cursor)
        window = await timeline.load_bounded_evidence(
            run_id=run_id, cursor=cursor,
            event_id=event.event_id if event else None,
            last_event_id=run.get("last_event_id"),
            last_receipt_id=run.get("last_evidence_receipt_id"),
        )
        if set(window) != {"current", "previous", "future"}:
            raise CommunityRunnerError("bounded evidence window is incomplete")
        _validate_last_evidence(
            run, timeline, window, run_id=run_id, holder_id=holder_id,
            cursor=cursor,
        )
        proof = _current_proof(
            run, event, window, run_id=run_id, holder_id=holder_id, cursor=cursor,
        )

        if run["state"] == run_lease.PAUSED and lease_mode != run_lease.MANUAL_STEP_MODE:
            return _no_action(run_id, "paused", cursor, claim["fence"])

        # A state/fence change after the snapshot must stop the tick before it
        # reports or performs work.
        owned = await run_lease.heartbeat(
            run_id,
            holder_id,
            claim["fence"],
            store=store,
            now=instant,
            ttl_seconds=ttl_seconds,
            mode=lease_mode,
        )
        if (
            owned.get("cursor") != cursor
            or owned.get("sim_minute") != run["sim_minute"]
            or owned.get("last_event_id") != run.get("last_event_id")
            or owned.get("last_evidence_receipt_id")
            != run.get("last_evidence_receipt_id")
        ):
            raise CommunityRunnerError("timeline snapshot is stale")
        if proof is not None:
            row = await community_cursor_commit.advance_cursor(
                run_id,
                holder_id,
                claim["fence"],
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
            return TickResult(
                run_id, "advanced", "advance_cursor_from_receipt", event.event_id,
                proof["receipt_id"], cursor, row["cursor"], claim["fence"], True,
            )
        if event is not None and _explicitly_blocked(event):
            return TickResult(
                run_id, "blocked", "none", None, None,
                cursor, cursor, claim["fence"], False,
            )
        if event is None:
            return _no_action(run_id, "complete", cursor, claim["fence"])
        if _event_minute(event) > run["sim_minute"]:
            return _no_action(run_id, "future", cursor, claim["fence"])
        result = await community_runner_step.execute_current(
            run_id, holder_id, claim["fence"], cursor, event,
            store=store,
            services=services,
            now=instant,
            ttl_seconds=ttl_seconds,
            clock=clock,
            lease_mode=lease_mode,
        )
        return TickResult(
            run_id, "executed", "execute_event_then_advance", result.event_id,
            result.receipt_id, result.cursor_before, result.cursor_after,
            claim["fence"], result.idempotent_replay,
        )
    except BaseException as exc:
        primary_error = exc
        raise
    finally:
        if claim is not None and (not supplied_claim or release_claim):
            try:
                await run_lease.release(
                    run_id, holder_id, claim["fence"], store=store, now=instant
                )
            except run_lease.RunLeaseError:
                if primary_error is None:
                    raise
