"""Pure shift-event planning for the living-community simulation.

The planner derives clock-in, handoff, clock-out, and department-coverage
events from :mod:`simulation.community_staffing`.  Its output is a plan, not
proof that anything happened: every event is ``status=planned`` with no
``receipt_id`` or ``executed_at``.  A runtime must execute the event through a
canonical service and attach the resulting receipt before claiming success.

No database, authentication, or ``User`` records are read or written here.
"""
from collections import Counter
from typing import Iterable

from simulation.community_staffing import (
    DEPARTMENT_LABELS,
    active_assignments,
    assignments_for_day,
)


PLANNED_ONLY = "Projected only; no action has executed and no receipt exists."
SHIFT_MILESTONE_TYPES = ("clock_in", "handoff", "clock_out")
_EVENT_ORDER = {
    "coverage_gap_present": 0,
    "coverage_gap_ended": 1,
    "clock_in": 2,
    "handoff": 3,
    "clock_out": 4,
    "coverage_gap_started": 5,
}


def _hhmm(minute: int) -> str:
    return f"{minute // 60:02d}:{minute % 60:02d}"


def _absolute_window(assignment: dict) -> tuple[int, int]:
    start = assignment["day_index"] * 1440 + assignment["start_minute"]
    end = assignment["day_index"] * 1440 + assignment["end_minute"]
    if assignment["spans_midnight"]:
        end += 1440
    return start, end


def _assignment_id(assignment: dict) -> str:
    return (
        f"sim:shift:{assignment['day_index']}:{assignment['actor_id']}:"
        f"{assignment['shift']}"
    )


def _session_id(assignment: dict) -> str:
    return (
        f"sim:worker-session:{assignment['day_index']}:"
        f"{assignment['actor_id']}:{assignment['shift']}"
    )


def _common(event_type: str, day_index: int, minute: int, subject: str) -> dict:
    return {
        "event_id": f"sim:shift-event:{day_index}:{minute:04d}:{event_type}:{subject}",
        "event_type": event_type,
        "day_index": day_index,
        "minute": minute,
        "time": _hhmm(minute),
        "status": "planned",
        "execution_state": "not_executed",
        "executed_at": None,
        "receipt_id": None,
        "requires_receipt_if_executed": True,
        "simulation_event": True,
        "truth": PLANNED_ONLY,
    }


def _staff_event(event_type: str, day_index: int, minute: int, assignment: dict, **extra) -> dict:
    """A canonical planned shift milestone for one synthetic worker."""
    assignment_id = _assignment_id(assignment)
    return {
        **_common(event_type, day_index, minute, assignment["actor_id"]),
        "stream_kind": "canonical_shift_milestone",
        "target_type": "staff_shift",
        "target_id": assignment_id,
        "shift_assignment_id": assignment_id,
        "session_id": _session_id(assignment),
        "assignment_day_index": assignment["day_index"],
        "actor_id": assignment["actor_id"],
        "actor_name": assignment["name"],
        "actor_type": assignment["actor_type"],
        "identity_basis": assignment["identity_basis"],
        "actor_simulated": assignment["simulated"],
        "department": assignment["department"],
        "department_label": assignment["department_label"],
        "job_role": assignment["job_role"],
        "shift": assignment["shift"],
        **extra,
    }


def _coverage_event(event_type: str, day_index: int, minute: int, department: str,
                    before: int, after: int) -> dict:
    """A planned simulator observation, not a staff action or fake identity."""
    return {
        **_common(event_type, day_index, minute, department),
        "stream_kind": "coverage_observation",
        "target_type": "department_coverage",
        "target_id": department,
        "actor_id": "system:simulation_planner",
        "actor_name": "simulation planner",
        "actor_type": "system",
        "identity_basis": "system",
        "actor_simulated": False,
        "department": department,
        "department_label": DEPARTMENT_LABELS[department],
        "coverage_before": before,
        "coverage_after": after,
    }


def _day_assignments(day_index: int) -> list[dict]:
    """Assignments that begin today plus overnight workers carried in."""
    carry_in = [row for row in active_assignments(day_index, 0)
                if row["day_index"] < day_index]
    return carry_in + assignments_for_day(day_index)


def _incoming(assignment: dict, at_absolute: int, candidates: list[dict]) -> list[str]:
    """Same-department workers on shift as this worker leaves."""
    ids = []
    for candidate in candidates:
        start, end = _absolute_window(candidate)
        if (candidate["department"] == assignment["department"]
                and candidate["actor_id"] != assignment["actor_id"]
                and start <= at_absolute < end):
            ids.append(candidate["actor_id"])
    return sorted(set(ids))


def planned_shift_milestones(assignment: dict, handoff_lead_minutes: int = 15,
                             candidates: list[dict] | None = None) -> list[dict]:
    """Return the one canonical clock-in/handoff/clock-out stream.

    Attendance/session projections reuse these exact event dictionaries and
    ids; they must not mint a second set of shift milestones.
    """
    if not 0 <= handoff_lead_minutes < 1440:
        raise ValueError("handoff_lead_minutes must be between 0 and 1439")
    start, end = _absolute_window(assignment)
    if candidates is None:
        end_day_index = end // 1440
        candidates = _day_assignments(end_day_index)

    moments = (
        ("clock_in", start, {}),
        ("handoff", end - handoff_lead_minutes, {
            "handoff_to_actor_ids": _incoming(assignment, end, candidates),
            "shift_end_minute": end % 1440,
        }),
        ("clock_out", end, {}),
    )
    events = []
    for event_type, absolute, extra in moments:
        day_index, minute = divmod(absolute, 1440)
        events.append(_staff_event(event_type, day_index, minute, assignment, **extra))
    return events


def _coverage_at(assignments: list[dict], absolute_minute: int) -> Counter:
    coverage = Counter()
    for assignment in assignments:
        start, end = _absolute_window(assignment)
        if start <= absolute_minute < end:
            coverage[assignment["department"]] += 1
    return coverage


def _coverage_events(day_index: int, assignments: list[dict], departments: Iterable[str]) -> list[dict]:
    start_of_day = day_index * 1440
    end_of_day = start_of_day + 1440
    events = []
    at_midnight = _coverage_at(assignments, start_of_day)
    for department in departments:
        if at_midnight[department] == 0:
            events.append(_coverage_event(
                "coverage_gap_present", day_index, 0, department, 0, 0,
            ))

    boundaries = set()
    for assignment in assignments:
        start, end = _absolute_window(assignment)
        if start_of_day < start < end_of_day:
            boundaries.add(start)
        if start_of_day < end < end_of_day:
            boundaries.add(end)
    for absolute in sorted(boundaries):
        minute = absolute - start_of_day
        before = _coverage_at(assignments, absolute - 1)
        after = _coverage_at(assignments, absolute)
        for department in departments:
            if before[department] == 0 and after[department] > 0:
                events.append(_coverage_event(
                    "coverage_gap_ended", day_index, minute, department,
                    before[department], after[department],
                ))
            elif before[department] > 0 and after[department] == 0:
                events.append(_coverage_event(
                    "coverage_gap_started", day_index, minute, department,
                    before[department], after[department],
                ))
    return events


def planned_events_for_day(day_index: int, handoff_lead_minutes: int = 15,
                           departments: Iterable[str] = DEPARTMENT_LABELS) -> list[dict]:
    """Derive one local day of planned events in deterministic order.

    Includes clock-out and handoff events for night workers whose shifts
    began on the prior day.  It does not mark events executed or receipted.
    """
    if day_index < 0:
        raise ValueError("day_index must be non-negative")
    if not 0 <= handoff_lead_minutes < 1440:
        raise ValueError("handoff_lead_minutes must be between 0 and 1439")
    departments = tuple(departments)
    unknown = set(departments) - set(DEPARTMENT_LABELS)
    if unknown:
        raise ValueError(f"unknown departments: {', '.join(sorted(unknown))}")

    assignments = _day_assignments(day_index)
    events = []
    for assignment in assignments:
        events.extend(
            event for event in planned_shift_milestones(
                assignment, handoff_lead_minutes, assignments,
            )
            if event["day_index"] == day_index
        )
    events.extend(_coverage_events(day_index, assignments, departments))
    return sorted(events, key=lambda event: (
        event["minute"], _EVENT_ORDER[event["event_type"]],
        event.get("department") or "", event["event_id"],
    ))


def event_counts(events: Iterable[dict]) -> dict[str, int]:
    """Small read helper for Live Operations summaries."""
    return dict(sorted(Counter(event["event_type"] for event in events).items()))
