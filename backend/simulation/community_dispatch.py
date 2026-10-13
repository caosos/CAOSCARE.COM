"""Pure coverage-aware dispatch planning for community routine events.

This module never assigns a worker, executes work, writes state, or calls a
provider.  It only distinguishes routine events that have department coverage
from events that must remain queued and unassigned until coverage resumes.
"""

from dataclasses import dataclass
from functools import lru_cache
from typing import Iterable, Optional

from simulation.community_routines import RoutineEvent, plan_first_24_hours
from simulation.community_staffing import DEPARTMENT_LABELS, active_assignments


READY_UNASSIGNED = "ready_unassigned"
QUEUED_UNASSIGNED = "queued_unassigned"
READY_TRUTH = (
    "Planning only: department coverage exists, but no worker is assigned and "
    "no work has been completed."
)
QUEUED_TRUTH = (
    "Queued and unassigned until department coverage resumes; no worker is "
    "assigned and no work has been completed."
)


@dataclass(frozen=True)
class RoutineDispatch:
    event_id: str
    resident_key: str
    routine: str
    department: str
    planned_day_index: int
    planned_minute: int
    dispatch_state: str
    ready_day_index: int
    ready_minute: int
    assigned_actor_id: Optional[str]
    truth: str

    @property
    def ready_time_hhmm(self) -> str:
        return f"{self.ready_minute // 60:02d}:{self.ready_minute % 60:02d}"


@lru_cache(maxsize=None)
def _on_shift_actor_ids(day_index: int, minute: int, department: str) -> tuple[str, ...]:
    return tuple(sorted(
        assignment["actor_id"]
        for assignment in active_assignments(day_index, minute)
        if assignment["department"] == department
    ))


def _next_coverage(event: RoutineEvent, max_queue_days: int) -> tuple[int, int]:
    start = event.day_index * 1440 + event.minute
    for absolute in range(start + 1, start + max_queue_days * 1440 + 1):
        day_index, minute = divmod(absolute, 1440)
        if _on_shift_actor_ids(day_index, minute, event.department):
            return day_index, minute
    raise ValueError(
        f"no {event.department} coverage within {max_queue_days} day(s) "
        f"after {event.event_id}"
    )


def plan_routine_dispatch(
    events: Optional[Iterable[RoutineEvent]] = None,
    *,
    max_queue_days: int = 7,
) -> tuple[RoutineDispatch, ...]:
    """Project coverage gates without assigning staff or claiming execution."""
    if max_queue_days < 1:
        raise ValueError("max_queue_days must be positive")
    source = tuple(plan_first_24_hours() if events is None else events)
    if len({event.event_id for event in source}) != len(source):
        raise ValueError("routine event ids must be unique")

    dispatches = []
    for event in source:
        if event.department not in DEPARTMENT_LABELS:
            raise ValueError(f"unknown department: {event.department}")
        if _on_shift_actor_ids(event.day_index, event.minute, event.department):
            state = READY_UNASSIGNED
            ready_day_index, ready_minute = event.day_index, event.minute
            truth = READY_TRUTH
        else:
            state = QUEUED_UNASSIGNED
            ready_day_index, ready_minute = _next_coverage(event, max_queue_days)
            truth = QUEUED_TRUTH
        dispatches.append(RoutineDispatch(
            event_id=event.event_id,
            resident_key=event.resident_key,
            routine=event.routine,
            department=event.department,
            planned_day_index=event.day_index,
            planned_minute=event.minute,
            dispatch_state=state,
            ready_day_index=ready_day_index,
            ready_minute=ready_minute,
            assigned_actor_id=None,
            truth=truth,
        ))
    return tuple(dispatches)
