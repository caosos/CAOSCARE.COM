"""Restart supervision for the RF bridge's rtl_433 child process.

Why this exists: when no SDR is plugged in, rtl_433 starts, prints its
banner, reports "No supported devices found." and exits within ~0.1 s.
The bridge used to respawn it immediately, forever - millions of spawns
and ~4 GB/day of identical log lines (RQ-008 RF log audit, 2026-10-05).

Policy:
  - A run is HEALTHY if rtl_433 stayed up at least HEALTHY_RUN_SECONDS or
    decoded at least one record. Healthy runs reset the backoff, so the
    existing stall watchdog (kill + USB reset after 90 s of silence, then
    respawn) keeps restarting at once, as before.
  - An unhealthy run waits 1, 2, 5, 10, 30, then 60 s (capped) before the
    next spawn. The wait is interruptible: SIGINT/SIGTERM set the stop
    event and the wait ends immediately.
  - Logging: the first failure (and any change of failure reason) is logged
    in full, once. Repeats are summarised every STATUS_INTERVAL_SECONDS.
    Recovery is logged once, with the number of failed attempts.
"""
from __future__ import annotations

import collections
import os
import sys
import threading
import time
from dataclasses import dataclass, field
from typing import Callable, Optional

BACKOFF_SCHEDULE = (1.0, 2.0, 5.0, 10.0, 30.0, 60.0)
# Must stay below the bridge's watchdog (90 s) so a run that lived until
# the watchdog fired counts as healthy and restarts immediately.
HEALTHY_RUN_SECONDS = float(os.environ.get("CAOS_HEALTHY_RUN_SECONDS", "30"))
STATUS_INTERVAL_SECONDS = float(os.environ.get("CAOS_RESTART_STATUS_SECONDS", "300"))


@dataclass
class RunResult:
    """What one rtl_433 run did. Built by run_rtl433()."""
    duration: float = 0.0             # seconds the process was up
    records: int = 0                  # JSON records decoded
    stalled: bool = False             # ended by the stall watchdog
    stopped: bool = False             # ended because shutdown was requested
    reason: str = ""                  # last useful stderr line / error text
    output_tail: list = field(default_factory=list)   # held-back output, printed once

    @property
    def healthy(self) -> bool:
        return self.records > 0 or self.duration >= HEALTHY_RUN_SECONDS

    @classmethod
    def failed(cls, reason: str) -> "RunResult":
        return cls(duration=0.0, reason=reason)


class RunOutput:
    """Where one run's chatter goes. Live: printed as it arrives (as before).
    Held (supervisor is quiet): kept back and handed to the supervisor, which
    prints it only for a new kind of failure. A held run that turns healthy
    goes live and prints what it held."""

    def __init__(self, live: bool, head: str):
        self.live = live
        self.head = head                           # the "[rf-bridge] spawning: ..." line
        self.held = collections.deque(maxlen=30)   # rtl_433 lines
        self.last_line = ""                        # newest rtl_433 line, for the reason
        self._lock = threading.Lock()
        if live:
            print(head, flush=True)

    def emit(self, line: str) -> None:
        with self._lock:
            self.last_line = line
            if self.live:
                print(f"[rtl_433] {line}", file=sys.stderr, flush=True)
            else:
                self.held.append(f"[rtl_433] {line}")

    def go_live(self) -> None:
        with self._lock:
            if self.live:
                return
            for line in [self.head, *self.held]:
                print(line, file=sys.stderr, flush=True)
            self.held.clear()
            self.live = True

    def tail(self) -> list:
        with self._lock:
            return [] if self.live else [self.head, *self.held]


class RestartSupervisor:
    """Decides how long to wait before the next rtl_433 spawn, and what to log."""

    def __init__(self, schedule=BACKOFF_SCHEDULE, log: Callable[[str], None] = print,
                 clock: Callable[[], float] = time.monotonic,
                 status_interval: float = None):
        self.schedule = tuple(schedule)
        self.log = log
        self.clock = clock
        self.status_interval = STATUS_INTERVAL_SECONDS if status_interval is None else status_interval
        self.failures = 0          # consecutive unhealthy runs
        self._last_reason: Optional[str] = None
        self._last_status: Optional[float] = None
        self._streak_started: Optional[float] = None

    @property
    def quiet(self) -> bool:
        """True while failing: per-spawn chatter (spawn line, rtl_433 banner)
        is buffered instead of printed, and only shown once on a new failure."""
        return self.failures > 0

    def delay_for(self, failures: int) -> float:
        return self.schedule[min(failures, len(self.schedule)) - 1] if failures > 0 else 0.0

    def after_run(self, result: RunResult) -> float:
        """Record a finished run; return seconds to wait before respawning."""
        now = self.clock()
        if result.healthy:
            if self.failures:
                self.log(f"[rf-bridge] rtl_433 recovered after {self.failures} failed start(s)")
            self.failures, self._last_reason, self._last_status, self._streak_started = 0, None, None, None
            return 0.0
        self.failures += 1
        delay = self.delay_for(self.failures)
        reason = result.reason or "rtl_433 exited"
        if self.failures == 1 or reason != self._last_reason:
            if self.failures == 1:
                self._streak_started = now
            for line in result.output_tail:
                self.log(line)
            self.log(f"[rf-bridge] rtl_433 failed after {result.duration:.1f}s: {reason} "
                     f"- retrying in {delay:.0f}s (backoff up to {self.schedule[-1]:.0f}s; "
                     f"repeats summarised every {self.status_interval:.0f}s)")
            self._last_reason, self._last_status = reason, now
        elif now - self._last_status >= self.status_interval:
            since = now - (self._streak_started or now)
            self.log(f"[rf-bridge] rtl_433 still failing: {self.failures} attempts over {since:.0f}s, "
                     f"last: {reason} - next retry in {delay:.0f}s")
            self._last_status = now
        return delay


def run_forever(run_once: Callable[[bool], RunResult], stop: threading.Event,
                supervisor: RestartSupervisor) -> None:
    """Spawn/supervise loop. `run_once(verbose)` runs rtl_433 once; returns
    when it ends. Never spins: every unhealthy run is followed by a wait
    that `stop` interrupts at once."""
    while not stop.is_set():
        result = run_once(not supervisor.quiet)
        if stop.is_set() or result.stopped:
            break
        delay = supervisor.after_run(result)
        if delay:
            stop.wait(delay)
