"""Validated immutable contracts shared by the living-community loop."""

from dataclasses import dataclass
from datetime import datetime, timezone
import os
from typing import Optional


RUNNING, PAUSED, STOPPED = "RUNNING", "PAUSED", "STOPPED"
HORIZON_MINUTES = 90 * 24 * 60
# Selectable acceleration. Speed only changes how fast simulated time advances;
# every event still executes one at a time with its receipt (none are skipped).
SPEEDS = (1, 10, 60, 600)
DEFAULT_SPEED = 60
SPEED_ENV = "CAOSCARE_LIVING_COMMUNITY_SPEED"


def configured_speed() -> int:
    """The operator-selected speed (default 60x); unknown values are refused."""
    raw = os.environ.get(SPEED_ENV, "").strip()
    if not raw:
        return DEFAULT_SPEED
    if not raw.isdigit() or int(raw) not in SPEEDS:
        raise ValueError(f"{SPEED_ENV} must be one of {SPEEDS}")
    return int(raw)


class CommunityLoopError(RuntimeError):
    """The loop cannot safely continue with the supplied runtime state."""


@dataclass(frozen=True)
class LoopConfig:
    acceleration: float = 60.0
    poll_seconds: float = 0.25
    blocked_backoff_seconds: float = 5.0
    error_backoff_seconds: float = 5.0
    horizon_minutes: int = HORIZON_MINUTES

    def __post_init__(self):
        numbers = (
            self.acceleration,
            self.poll_seconds,
            self.blocked_backoff_seconds,
            self.error_backoff_seconds,
        )
        if any(isinstance(value, bool) or value <= 0 for value in numbers):
            raise CommunityLoopError("loop rates and delays must be positive")
        if (
            isinstance(self.horizon_minutes, bool)
            or self.horizon_minutes != HORIZON_MINUTES
        ):
            raise CommunityLoopError("living-community horizon must be exactly 90 days")


@dataclass(frozen=True)
class LoopStatus:
    run_id: str
    holder_id: str
    phase: str = "starting"
    run_state: Optional[str] = None
    cursor: int = 0
    sim_minute: int = 0
    ticks_started: int = 0
    ticks_finished: int = 0
    events_executed: int = 0
    receipts_recovered: int = 0
    blocked_count: int = 0
    error_count: int = 0
    consecutive_errors: int = 0
    last_tick_status: Optional[str] = None
    last_event_id: Optional[str] = None
    last_receipt_id: Optional[str] = None
    last_error: Optional[str] = None
    started_at: Optional[str] = None
    updated_at: Optional[str] = None
    finished_at: Optional[str] = None


def utc(clock) -> datetime:
    instant = clock()
    if not isinstance(instant, datetime) or instant.tzinfo is None:
        raise CommunityLoopError("loop clock must return a timezone-aware datetime")
    return instant.astimezone(timezone.utc)


def validate_run(run_id: str, row: Optional[dict], horizon: int) -> dict:
    if not isinstance(row, dict) or row.get("run_id") != run_id:
        raise CommunityLoopError("run loader did not return the requested run")
    if row.get("state") not in (RUNNING, PAUSED, STOPPED):
        raise CommunityLoopError("run state must be RUNNING, PAUSED, or STOPPED")
    for key in ("cursor", "sim_minute"):
        value = row.get(key)
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise CommunityLoopError(f"run {key} must be a non-negative integer")
    if row["sim_minute"] > horizon:
        raise CommunityLoopError("run simulated time is beyond the 90-day horizon")
    return row
