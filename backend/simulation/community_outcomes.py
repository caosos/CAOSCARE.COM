"""Deterministic, planned-only outcomes for community routine events.

These records are scenario expectations, not operational facts or receipts.
The module performs no database/provider work.  A later simulator driver must
execute an event through its safe canonical adapter and use the resulting
receipt—not this plan—as evidence of what actually happened.
"""

from dataclasses import dataclass
from hashlib import sha256
from typing import Iterable, Optional

from simulation.community_dispatch import QUEUED_UNASSIGNED, plan_routine_dispatch
from simulation.community_routines import RoutineEvent, plan_first_24_hours
from simulation.community_service_model import is_meal


PLANNED_ONLY = "simulated_plan_only"
OUTCOMES = (
    "completed", "resident_refused", "resident_requested_reschedule",
    QUEUED_UNASSIGNED,
)


@dataclass(frozen=True)
class RoutineOutcome:
    """One expected scenario result; never evidence of real execution."""

    outcome_id: str
    event_id: str
    resident_key: str
    routine: str
    department: str
    planned_disposition: str
    dispatch_state: str
    planned_resolution_day_index: int
    planned_resolution_minute: int
    summary: str
    truth_boundary: str
    evidence_label: str = PLANNED_ONLY
    represents_execution: bool = False
    assigned_actor_id: Optional[str] = None
    queued_until_day_index: Optional[int] = None
    queued_until_minute: Optional[int] = None
    rescheduled_event_id: Optional[str] = None
    rescheduled_to_minute: Optional[int] = None

    @property
    def planned_resolution_hhmm(self) -> str:
        return f"{self.planned_resolution_minute // 60:02d}:{self.planned_resolution_minute % 60:02d}"

    @property
    def rescheduled_to_hhmm(self) -> Optional[str]:
        if self.rescheduled_to_minute is None:
            return None
        return f"{self.rescheduled_to_minute // 60:02d}:{self.rescheduled_to_minute % 60:02d}"


def _score(event: RoutineEvent, seed: str) -> int:
    """Stable across processes; unlike Python's randomized built-in hash."""
    return int.from_bytes(sha256(f"{seed}:{event.event_id}".encode("utf-8")).digest()[:4], "big")


def _disposition(event: RoutineEvent, score: int) -> str:
    # Roughly 10% refusals and 5% reschedules produces ordinary friction
    # without making a routine day look catastrophically unsuccessful.
    candidate = "resident_refused" if score % 20 in (0, 1) else (
        "resident_requested_reschedule" if score % 20 == 2 else "completed"
    )
    return candidate if candidate in event.possible_outcomes else "completed"


def _resolution_minute(event: RoutineEvent, disposition: str, score: int) -> int:
    if disposition == "resident_requested_reschedule":
        delay = 2 + score % 4
    elif disposition == "resident_refused":
        delay = 3 + score % 5
    else:
        delay = 8 + score % 23
    return min(event.minute + delay, 24 * 60 - 1)


def _reschedule_minute(event: RoutineEvent, score: int) -> int:
    # 30–89 minutes later and always within the same 24-hour plan.
    return min(event.minute + 30 + score % 60, 24 * 60 - 1)


def _summary(event: RoutineEvent, disposition: str) -> tuple[str, str]:
    medication = "medication_reminder" in event.routine
    meal = is_meal(event.routine)

    if medication:
        action = {
            "completed": "the reminder would be delivered",
            "resident_refused": "the resident would decline the reminder",
            "resident_requested_reschedule": "the resident would ask for the reminder later",
        }[disposition]
        return (
            f"Planned simulated result: {action}; medication use remains unknown.",
            "Reminder outcome only. Never infer medication administration, ingestion, dose completion, or adherence.",
        )
    if meal:
        action = {
            "completed": "the meal-service task would be completed",
            "resident_refused": "the resident would decline the offered meal service",
            "resident_requested_reschedule": "the resident would ask for meal service later",
        }[disposition]
        return (
            f"Planned simulated result: {action}; food intake remains unknown.",
            "Service outcome only. Never infer what or how much the resident consumed.",
        )

    action = {
        "completed": "the task would be completed",
        "resident_refused": "the resident would decline the offered task",
        "resident_requested_reschedule": "the resident would ask to reschedule the task",
    }[disposition]
    return (
        f"Planned simulated result: {action}.",
        f"{event.truth_boundary} This plan is not execution evidence.",
    )


def plan_routine_outcomes(
    events: Optional[Iterable[RoutineEvent]] = None,
    *,
    seed: str = "living-community-first-day-v1",
) -> tuple[RoutineOutcome, ...]:
    """Plan believable results for routine events without executing them."""
    if not seed:
        raise ValueError("seed must be non-empty")
    source = tuple(plan_first_24_hours() if events is None else events)
    if len({event.event_id for event in source}) != len(source):
        raise ValueError("routine event ids must be unique")
    dispatch_by_event = {
        dispatch.event_id: dispatch for dispatch in plan_routine_dispatch(source)
    }

    outcomes = []
    for event in source:
        dispatch = dispatch_by_event[event.event_id]
        score = _score(event, seed)
        disposition = (
            QUEUED_UNASSIGNED
            if dispatch.dispatch_state == QUEUED_UNASSIGNED
            else _disposition(event, score)
        )
        if disposition == QUEUED_UNASSIGNED:
            summary = (
                "Planned dispatch result: queued and unassigned until "
                f"day {dispatch.ready_day_index} at {dispatch.ready_time_hhmm}; "
                "no work has been completed."
            )
            boundary = dispatch.truth
            resolution_day_index = dispatch.ready_day_index
            resolution_minute = dispatch.ready_minute
        else:
            summary, boundary = _summary(event, disposition)
            resolution_day_index = event.day_index
            resolution_minute = _resolution_minute(event, disposition, score)
        rescheduled_event_id = None
        rescheduled_to_minute = None
        if disposition == "resident_requested_reschedule":
            rescheduled_event_id = f"{event.event_id}:rescheduled-1"
            rescheduled_to_minute = _reschedule_minute(event, score)
        outcomes.append(RoutineOutcome(
            outcome_id=f"outcome:{event.event_id}",
            event_id=event.event_id,
            resident_key=event.resident_key,
            routine=event.routine,
            department=event.department,
            planned_disposition=disposition,
            dispatch_state=dispatch.dispatch_state,
            planned_resolution_day_index=resolution_day_index,
            planned_resolution_minute=resolution_minute,
            summary=summary,
            truth_boundary=boundary,
            assigned_actor_id=None,
            queued_until_day_index=(
                dispatch.ready_day_index if disposition == QUEUED_UNASSIGNED else None
            ),
            queued_until_minute=(
                dispatch.ready_minute if disposition == QUEUED_UNASSIGNED else None
            ),
            rescheduled_event_id=rescheduled_event_id,
            rescheduled_to_minute=rescheduled_to_minute,
        ))
    return tuple(outcomes)
