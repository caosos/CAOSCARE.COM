"""Cancellable in-process driver for the fenced living-community runner.

Nothing in this module starts itself, exposes a route, selects a database, or
contacts a provider.  Callers inject every side-effect boundary.  The driver
advances a durable simulation clock and asks the existing runner for exactly
one fenced event at a time.
"""

import asyncio
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from typing import Awaitable, Callable, Optional

from simulation import community_runner
from simulation.community_loop_contract import (
    HORIZON_MINUTES,
    PAUSED,
    RUNNING,
    STOPPED,
    CommunityLoopError,
    LoopConfig,
    LoopStatus,
    utc as _utc,
    validate_run as _validate_run,
)


RunLoader = Callable[..., Awaitable[Optional[dict]]]
ClockAdvancer = Callable[..., Awaitable[dict]]
RunCompleter = Callable[..., Awaitable[dict]]
TickFunction = Callable[..., Awaitable[community_runner.TickResult]]
SleepFunction = Callable[[float], Awaitable[None]]
ClockFunction = Callable[[], datetime]


@dataclass
class _Handle:
    status: LoopStatus
    cancel: asyncio.Event
    wake: asyncio.Event
    task: Optional[asyncio.Task] = None


_ACTIVE: dict[str, asyncio.Task] = {}


def is_active(run_id: str) -> bool:
    """Return process-local loop ownership without creating or stopping work."""
    task = _ACTIVE.get(run_id)
    return bool(task and not task.done())


class CommunityLoopManager:
    """Own explicit loop tasks and immutable status snapshots for the UI."""

    def __init__(
        self, *, store, timeline, services, load_run: RunLoader,
        advance_sim_clock: ClockAdvancer, complete_run: RunCompleter,
        tick: TickFunction = community_runner.tick,
        clock: ClockFunction = lambda: datetime.now(timezone.utc),
        sleep: SleepFunction = asyncio.sleep,
        config: LoopConfig = LoopConfig(),
    ):
        self.store, self.timeline, self.services = store, timeline, services
        self.load_run = load_run
        self.advance_sim_clock, self.complete_run = advance_sim_clock, complete_run
        self.tick, self.clock, self.sleep, self.config = tick, clock, sleep, config
        self._handles: dict[str, _Handle] = {}

    def start(self, run_id: str, holder_id: str) -> bool:
        """Reserve one process-local driver; return False when already owned."""
        if not run_id or not holder_id:
            raise CommunityLoopError("run_id and holder_id are required")
        active = _ACTIVE.get(run_id)
        if active and not active.done():
            return False
        now = _utc(self.clock).isoformat()
        status = LoopStatus(run_id, holder_id, started_at=now, updated_at=now)
        handle = _Handle(status, asyncio.Event(), asyncio.Event())
        task = asyncio.create_task(self._drive(handle))
        handle.task = task
        self._handles[run_id] = handle
        _ACTIVE[run_id] = task
        task.add_done_callback(lambda done: self._release(run_id, done))
        return True

    def wake(self, run_id: str) -> None:
        """Interrupt polling after a control transition such as resume."""
        handle = self._handles.get(run_id)
        if handle:
            handle.wake.set()

    async def cancel(self, run_id: str) -> Optional[LoopStatus]:
        """Request graceful cancellation; an in-flight fenced tick may finish."""
        handle = self._handles.get(run_id)
        if not handle:
            return None
        handle.cancel.set()
        handle.wake.set()
        if handle.task:
            await handle.task
        return handle.status

    async def wait(self, run_id: str) -> Optional[LoopStatus]:
        handle = self._handles.get(run_id)
        if not handle:
            return None
        if handle.task:
            await handle.task
        return handle.status

    def status(self, run_id: str) -> Optional[LoopStatus]:
        """Return an immutable snapshot; callers cannot mutate loop truth."""
        handle = self._handles.get(run_id)
        return replace(handle.status) if handle else None

    def _release(self, run_id: str, task: asyncio.Task) -> None:
        if _ACTIVE.get(run_id) is task:
            _ACTIVE.pop(run_id, None)

    def _set(self, handle: _Handle, **changes) -> None:
        changes.setdefault("updated_at", _utc(self.clock).isoformat())
        handle.status = replace(handle.status, **changes)

    async def _wait(self, handle: _Handle, delay: float) -> None:
        if handle.cancel.is_set():
            return
        if handle.wake.is_set():
            handle.wake.clear()
            return
        sleeper = asyncio.create_task(self.sleep(delay))
        signal = asyncio.create_task(handle.wake.wait())
        cancelled = asyncio.create_task(handle.cancel.wait())
        tasks = {sleeper, signal, cancelled}
        try:
            done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
            if signal in done:
                handle.wake.clear()
            if sleeper in done:
                sleeper.result()
        finally:
            pending = {task for task in tasks if not task.done()}
            for task in pending:
                task.cancel()
            if pending:
                await asyncio.gather(*pending, return_exceptions=True)

    async def _load_running(self, handle: _Handle) -> Optional[dict]:
        row = _validate_run(
            handle.status.run_id,
            await self.load_run(run_id=handle.status.run_id),
            self.config.horizon_minutes,
        )
        self._set(
            handle, run_state=row["state"], cursor=row["cursor"],
            sim_minute=row["sim_minute"],
        )
        if row["state"] == STOPPED:
            self._set(handle, phase="stopped")
            return None
        if row["state"] == PAUSED:
            self._set(handle, phase="paused", consecutive_errors=0)
            await self._wait(handle, self.config.poll_seconds)
            return None
        advanced = await self.advance_sim_clock(
            run_id=handle.status.run_id, observed_run=row,
            observed_at=_utc(self.clock), acceleration=self.config.acceleration,
            horizon_minutes=self.config.horizon_minutes,
        )
        advanced = _validate_run(handle.status.run_id, advanced,
                                 self.config.horizon_minutes)
        self._set(
            handle, run_state=advanced["state"], cursor=advanced["cursor"],
            sim_minute=advanced["sim_minute"],
        )
        if advanced["state"] != RUNNING:
            self._set(handle, phase=advanced["state"].lower())
            if advanced["state"] == PAUSED:
                await self._wait(handle, self.config.poll_seconds)
            return None
        return advanced

    async def _drive(self, handle: _Handle) -> None:
        try:
            while not handle.cancel.is_set():
                try:
                    row = await self._load_running(handle)
                    if row is None:
                        if handle.status.phase == "stopped":
                            break
                        continue
                    self._set(
                        handle, phase="running",
                        ticks_started=handle.status.ticks_started + 1,
                    )
                    result = await self.tick(
                        handle.status.run_id, handle.status.holder_id,
                        store=self.store, timeline=self.timeline,
                        services=self.services, now=_utc(self.clock),
                        clock=self.clock,
                    )
                    changes = {
                        "ticks_finished": handle.status.ticks_finished + 1,
                        "cursor": result.cursor_after,
                        "last_tick_status": result.status,
                        "last_event_id": result.event_id,
                        "last_receipt_id": result.receipt_id,
                        "last_error": None,
                        "consecutive_errors": 0,
                    }
                    if result.status == "executed":
                        changes["events_executed"] = handle.status.events_executed + 1
                    elif result.status == "advanced":
                        changes["receipts_recovered"] = handle.status.receipts_recovered + 1
                    self._set(handle, **changes)
                    if result.status == "blocked":
                        self._set(
                            handle, phase="blocked",
                            blocked_count=handle.status.blocked_count + 1,
                        )
                        await self._wait(handle, self.config.blocked_backoff_seconds)
                    elif result.status == "paused":
                        self._set(handle, phase="paused")
                        await self._wait(handle, self.config.poll_seconds)
                    elif result.status == "stopped":
                        self._set(handle, phase="stopped")
                        break
                    elif result.status == "complete":
                        completed = await self.complete_run(
                            run_id=handle.status.run_id,
                            observed_run=row,
                            observed_at=_utc(self.clock),
                            horizon_minutes=self.config.horizon_minutes,
                        )
                        completed = _validate_run(
                            handle.status.run_id, completed,
                            self.config.horizon_minutes,
                        )
                        if (
                            completed["state"] != STOPPED
                            or completed["cursor"] != result.cursor_after
                            or completed["sim_minute"] != self.config.horizon_minutes
                            or completed.get("terminal_reason") != "completed"
                            or not completed.get("completion_receipt_id")
                        ):
                            raise CommunityLoopError(
                                "completion did not persist the exact terminal boundary"
                            )
                        self._set(
                            handle, phase="complete", run_state=STOPPED,
                            cursor=completed["cursor"],
                            sim_minute=completed["sim_minute"],
                            last_receipt_id=completed["completion_receipt_id"],
                        )
                        break
                    elif result.status not in ("executed", "advanced"):
                        self._set(handle, phase=result.status)
                        await self._wait(handle, self.config.poll_seconds)
                except Exception as exc:
                    phase = "inconsistent" if "inconsistent" in str(exc).lower() else "error"
                    self._set(
                        handle, phase=phase, last_error=f"{type(exc).__name__}: {exc}",
                        error_count=handle.status.error_count + 1,
                        consecutive_errors=handle.status.consecutive_errors + 1,
                    )
                    await self._wait(handle, self.config.error_backoff_seconds)
            if handle.cancel.is_set():
                self._set(handle, phase="cancelled")
        finally:
            self._set(handle, finished_at=_utc(self.clock).isoformat())
