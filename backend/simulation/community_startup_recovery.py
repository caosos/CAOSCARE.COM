"""Default-off, injected startup recovery for one living-community run.

Importing this module performs no reads, writes, task creation, route wiring,
or provider work.  An application composition root must explicitly enable it,
prove transaction/index readiness, and call ``recover``.
"""

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
import math
from typing import Awaitable, Callable, Optional

from simulation import community_runner
from simulation.community_blueprint import COMMUNITY_ID, SIMULATION_SCOPE
from simulation.community_run_lifecycle import RUN_KIND
from simulation.community_startup_capability import (
    CapabilityProbe,
    capability_blockers,
    shared_capability_probe,
)
from simulation.community_startup_receipts import recovery_key, write_or_verify


class CommunityStartupRecoveryError(RuntimeError):
    """Startup recovery refused to start community work."""


@dataclass(frozen=True)
class StartupRecoveryConfig:
    enabled: bool = False
    startup_id: Optional[str] = None
    holder_id: str = "living-community-startup-runner"
    acceleration: float = 60.0
    horizon_minutes: int = 90 * 24 * 60

    def __post_init__(self):
        if (
            isinstance(self.acceleration, bool)
            or not isinstance(self.acceleration, (int, float))
            or not math.isfinite(self.acceleration)
            or self.acceleration <= 0
        ):
            raise CommunityStartupRecoveryError("startup acceleration must be positive")
        if self.horizon_minutes != 90 * 24 * 60:
            raise CommunityStartupRecoveryError("startup recovery horizon must be exactly 90 days")


@dataclass(frozen=True)
class StartupRecoveryResult:
    status: str
    run_id: Optional[str] = None
    decision_receipt_id: Optional[str] = None
    outcome_receipt_id: Optional[str] = None
    reconcile_status: Optional[str] = None
    loop_started: bool = False
    idempotent_replay: bool = False
    blockers: tuple[str, ...] = ()


ClockAdvancer = Callable[..., Awaitable[dict]]
ReconcileTick = Callable[..., Awaitable[object]]
Clock = Callable[[], datetime]


def bounded_runner_reconciler(
    *, store, timeline, services, tick=community_runner.tick,
    clock: Clock = lambda: datetime.now(timezone.utc),
) -> ReconcileTick:
    """Bind the canonical bounded runner without choosing a database."""
    async def reconcile(run_id: str, holder_id: str, *, now: datetime):
        return await tick(
            run_id, holder_id, store=store, timeline=timeline,
            services=services, now=now, clock=clock,
        )

    return reconcile


def _now(clock: Clock) -> datetime:
    value = clock()
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise CommunityStartupRecoveryError("startup clock must be timezone-aware")
    return value.astimezone(timezone.utc)


def _text(value, label: str) -> str:
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > 180:
        raise CommunityStartupRecoveryError(f"{label} must be 1-180 characters")
    return value.strip()


def _coordinate(value, label: str, maximum: Optional[int] = None) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise CommunityStartupRecoveryError(f"run {label} is invalid")
    if maximum is not None and value > maximum:
        raise CommunityStartupRecoveryError(f"run {label} exceeds the configured horizon")
    return value


def _validate_run(row: dict, expected_id: Optional[str], horizon: int) -> dict:
    if not isinstance(row, dict):
        raise CommunityStartupRecoveryError("startup recovery did not load a run")
    run_id = _text(row.get("run_id"), "run_id")
    expected = {
        "state": "RUNNING",
        "simulation_scope": SIMULATION_SCOPE,
        "simulation_community_id": COMMUNITY_ID,
        "run_kind": RUN_KIND,
    }
    if expected_id is not None and run_id != expected_id:
        raise CommunityStartupRecoveryError("startup recovery loaded a different run")
    if any(row.get(key) != value for key, value in expected.items()):
        raise CommunityStartupRecoveryError("running run scope, community, or kind is invalid")
    _coordinate(row.get("cursor"), "cursor")
    _coordinate(row.get("sim_minute"), "simulated minute", horizon)
    if not row.get("origin_receipt_id") or not row.get("last_transition_receipt_id"):
        raise CommunityStartupRecoveryError("running run has no lifecycle provenance")
    return dict(row)


def _reconcile_proof(result, run: dict) -> dict:
    required = ("run_id", "status", "cursor_before", "cursor_after", "receipt_id")
    values = {field: getattr(result, field, None) for field in required}
    if values["run_id"] != run["run_id"]:
        raise CommunityStartupRecoveryError("bounded recovery reconciled a different run")
    before = _coordinate(values["cursor_before"], "recovery cursor")
    after = _coordinate(values["cursor_after"], "recovered cursor")
    if before != run["cursor"] or after not in (before, before + 1):
        raise CommunityStartupRecoveryError("bounded recovery crossed more than one event")
    status = _text(values["status"], "reconcile status")
    action = getattr(result, "action", None)
    actions = {
        "executed": "execute_event_then_advance",
        "advanced": "advance_cursor_from_receipt",
        "future": "none", "blocked": "none", "complete": "none",
        "paused": "none", "stopped": "none",
    }
    if status not in actions or action != actions[status]:
        raise CommunityStartupRecoveryError("bounded recovery status/action is invalid")
    if action in ("execute_event_then_advance", "advance_cursor_from_receipt"):
        _text(values["receipt_id"], "reconcile receipt_id")
        if after != before + 1:
            raise CommunityStartupRecoveryError("receipt-backed recovery did not advance once")
    elif after != before:
        raise CommunityStartupRecoveryError("cursor advanced without receipt-backed recovery")
    return {
        "status": status,
        "action": action,
        "cursor_before": before,
        "cursor_after": after,
        "receipt_id": values["receipt_id"],
    }


class CommunityStartupRecoveryCoordinator:
    """Serializes one explicit, capability-gated process startup recovery."""

    def __init__(
        self, *, store, loop_manager,
        advance_sim_clock: ClockAdvancer, reconcile_tick: ReconcileTick,
        capability_probe: Optional[CapabilityProbe] = None,
        config: StartupRecoveryConfig = StartupRecoveryConfig(),
        clock: Clock = lambda: datetime.now(timezone.utc),
    ):
        self.store, self.loop_manager = store, loop_manager
        self.capability_probe = capability_probe or shared_capability_probe(store=store)
        self.advance_sim_clock, self.reconcile_tick = advance_sim_clock, reconcile_tick
        self.config, self.clock = config, clock
        self._lock = asyncio.Lock()
        self._active: Optional[StartupRecoveryResult] = None

    def _active_result(self) -> Optional[StartupRecoveryResult]:
        if not self._active or not self._active.run_id:
            return None
        status = self.loop_manager.status(self._active.run_id)
        if status is not None and not getattr(status, "finished_at", None):
            return StartupRecoveryResult(
                **{**self._active.__dict__, "idempotent_replay": True}
            )
        self._active = None
        return None

    async def _running_run(self) -> Optional[dict]:
        query = {
            "state": "RUNNING",
            "simulation_scope": SIMULATION_SCOPE,
            "simulation_community_id": COMMUNITY_ID,
            "run_kind": RUN_KIND,
        }
        rows = await self.store.sim_runs.find(query, {"_id": 0}).to_list(2)
        if len(rows) > 1:
            raise CommunityStartupRecoveryError("multiple exact RUNNING community runs found")
        return None if not rows else _validate_run(
            rows[0], None, self.config.horizon_minutes,
        )

    async def recover(self) -> StartupRecoveryResult:
        async with self._lock:
            active = self._active_result()
            if active:
                return active
            if self.config.enabled is not True:
                return StartupRecoveryResult(status="disabled", blockers=("feature_disabled",))
            startup_id = _text(self.config.startup_id, "startup_id")
            holder_id = _text(self.config.holder_id, "holder_id")
            capability = await self.capability_probe()
            blockers = capability_blockers(capability)
            if blockers:
                return StartupRecoveryResult(status="blocked", blockers=blockers)

            run = await self._running_run()
            if run is None:
                return StartupRecoveryResult(status="no_running_run")
            instant = _now(self.clock)
            key = recovery_key(startup_id, run["run_id"])
            requested = await write_or_verify(
                store=self.store, run=run, key=key, phase="requested",
                decision="reconcile_and_start", when=instant,
                parent_receipt_id=run["last_transition_receipt_id"],
            )
            advanced = await self.advance_sim_clock(
                run_id=run["run_id"], observed_run=run, observed_at=instant,
                acceleration=self.config.acceleration,
                horizon_minutes=self.config.horizon_minutes,
            )
            advanced = _validate_run(
                advanced, run["run_id"], self.config.horizon_minutes,
            )
            tick = await self.reconcile_tick(
                run["run_id"], holder_id, now=instant,
            )
            proof = _reconcile_proof(tick, advanced)
            current = await self._running_run()
            current = _validate_run(
                current, run["run_id"], self.config.horizon_minutes,
            )
            started = self.loop_manager.start(run["run_id"], holder_id)
            decision = "loop_started" if started else "loop_already_active"
            try:
                outcome = await write_or_verify(
                    store=self.store, run=current, key=key, phase="started",
                    decision=decision, when=_now(self.clock),
                    parent_receipt_id=requested["receipt_id"], reconcile=proof,
                )
            except BaseException:
                if started:
                    await self.loop_manager.cancel(run["run_id"])
                raise
            result = StartupRecoveryResult(
                status="started" if started else "already_active",
                run_id=run["run_id"],
                decision_receipt_id=requested["receipt_id"],
                outcome_receipt_id=outcome["receipt_id"],
                reconcile_status=proof["status"], loop_started=started,
            )
            self._active = result
            return result
