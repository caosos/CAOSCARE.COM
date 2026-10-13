"""Planning-only synthetic worker attendance and session projection.

Every one of the 50 synthetic workers gets one state per projected day.  An
on-duty state contains attendance-owned simulator session markers plus exact
references to the canonical clock-in, handoff, and clock-out events from
``community_shift_events``.  An off-duty state contains no invented activity.

"Login" here is explicitly a simulation-session plan.  It does not create a
``User``, authenticate, mint a token, write a database record, or prove that
the event occurred.  A future runtime must use canonical services and attach
receipts before reporting execution.
"""
from collections import Counter
from datetime import date, datetime, time, timedelta
from typing import Iterable

from simulation.community_staffing import WORKERS, assignments_for_day
from simulation.community_shift_events import (
    SHIFT_MILESTONE_TYPES,
    planned_shift_milestones,
)


PLANNING_TRUTH = "Planned only; not authenticated, executed, or receipted."
MILESTONE_TYPES = (
    "planned_login",
    SHIFT_MILESTONE_TYPES[0],
    "assignment_acceptance",
    *SHIFT_MILESTONE_TYPES[1:],
)
SESSION_MILESTONE_TYPES = ("planned_login", "assignment_acceptance")


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


def _absolute_window(assignment: dict) -> tuple[int, int]:
    start = assignment["day_index"] * 1440 + assignment["start_minute"]
    end = assignment["day_index"] * 1440 + assignment["end_minute"]
    if assignment["spans_midnight"]:
        end += 1440
    return start, end


def _position(absolute_minute: int) -> dict:
    day_index, minute = divmod(absolute_minute, 1440)
    return {
        "day_index": day_index,
        "minute": minute,
        "time": f"{minute // 60:02d}:{minute % 60:02d}",
    }


def _session_milestone(event_type: str, absolute_minute: int, assignment: dict) -> dict:
    """Build attendance-owned intent, never a duplicate shift milestone."""
    if event_type not in SESSION_MILESTONE_TYPES:
        raise ValueError(f"attendance does not own {event_type} milestones")
    position = _position(absolute_minute)
    event = {
        "event_id": (
            f"sim:attendance-event:{position['day_index']}:{position['minute']:04d}:"
            f"{event_type}:{assignment['actor_id']}"
        ),
        "event_type": event_type,
        **position,
        "status": "planned",
        "execution_state": "not_executed",
        "executed_at": None,
        "receipt_id": None,
        "requires_receipt_if_executed": True,
        "truth": PLANNING_TRUTH,
        "stream_kind": "attendance_session_intent",
        "session_id": _session_id(assignment),
        "shift_assignment_id": _assignment_id(assignment),
        "actor_id": assignment["actor_id"],
        "actor_name": assignment["name"],
        "actor_type": assignment["actor_type"],
        "identity_basis": assignment["identity_basis"],
        "actor_simulated": assignment["simulated"],
        "department": assignment["department"],
        "job_role": assignment["job_role"],
        "shift": assignment["shift"],
    }
    if event_type == "planned_login":
        event.update({
            "login_kind": "simulation_session_marker",
            "authentication_performed": False,
            "creates_user_or_token": False,
        })
    if event_type == "assignment_acceptance":
        event.update({
            "assignment_scope": "shift_only",
            "task_ids": [],
            "accepts_canonical_task": False,
        })
    return event


def session_plan(assignment: dict, *, login_lead_minutes: int = 10,
                 acceptance_delay_minutes: int = 5,
                 handoff_lead_minutes: int = 15) -> dict:
    """Create five planned milestones for one scheduled worker shift."""
    for name, value in (
        ("login_lead_minutes", login_lead_minutes),
        ("acceptance_delay_minutes", acceptance_delay_minutes),
        ("handoff_lead_minutes", handoff_lead_minutes),
    ):
        if value < 0:
            raise ValueError(f"{name} must be non-negative")
    start, end = _absolute_window(assignment)
    if start - login_lead_minutes < assignment["day_index"] * 1440:
        raise ValueError("login lead crosses before the assignment day")
    if start + acceptance_delay_minutes >= end:
        raise ValueError("assignment acceptance must occur before shift end")
    if end - handoff_lead_minutes <= start:
        raise ValueError("handoff must occur after shift start")
    shift_milestones = {
        event["event_type"]: event
        for event in planned_shift_milestones(assignment, handoff_lead_minutes)
    }
    milestones = [
        _session_milestone("planned_login", start - login_lead_minutes, assignment),
        shift_milestones["clock_in"],
        _session_milestone(
            "assignment_acceptance", start + acceptance_delay_minutes, assignment,
        ),
        shift_milestones["handoff"],
        shift_milestones["clock_out"],
    ]
    return {
        "session_id": _session_id(assignment),
        "shift_assignment_id": _assignment_id(assignment),
        "attendance_state": "scheduled",
        "status": "planned",
        "execution_state": "not_executed",
        "receipt_ids": [],
        "truth": PLANNING_TRUTH,
        "actor_id": assignment["actor_id"],
        "actor_name": assignment["name"],
        "actor_type": assignment["actor_type"],
        "identity_basis": assignment["identity_basis"],
        "actor_simulated": assignment["simulated"],
        "department": assignment["department"],
        "job_role": assignment["job_role"],
        "shift": assignment["shift"],
        "assignment_day_index": assignment["day_index"],
        "shift_milestones_source": "simulation.community_shift_events",
        "milestones": milestones,
    }


def worker_states_for_day(day_index: int) -> list[dict]:
    """Return exactly one planned attendance state for each of 50 workers."""
    if day_index < 0:
        raise ValueError("day_index must be non-negative")
    scheduled = {row["actor_id"]: row for row in assignments_for_day(day_index)}
    states = []
    for worker in WORKERS:
        assignment = scheduled.get(worker["actor_id"])
        if assignment:
            states.append(session_plan(assignment))
        else:
            states.append({
                "session_id": None,
                "shift_assignment_id": None,
                "attendance_state": "off_duty",
                "status": "planned",
                "execution_state": "not_executed",
                "receipt_ids": [],
                "truth": PLANNING_TRUTH,
                "actor_id": worker["actor_id"],
                "actor_name": worker["name"],
                "actor_type": worker["actor_type"],
                "identity_basis": worker["identity_basis"],
                "actor_simulated": worker["simulated"],
                "department": worker["department"],
                "job_role": worker["job_role"],
                "assignment_day_index": day_index,
                "milestones": [],
            })
    return states


def _with_dates(state: dict, start_date: date) -> dict:
    state_date = start_date + timedelta(days=state["assignment_day_index"])
    dated = {**state, "date": state_date.isoformat()}
    dated["milestones"] = []
    for milestone in state["milestones"]:
        event_date = start_date + timedelta(days=milestone["day_index"])
        at = datetime.combine(event_date, time.min) + timedelta(minutes=milestone["minute"])
        dated["milestones"].append({**milestone, "planned_at": at.isoformat()})
    return dated


def project_worker_attendance(start_date: date | str, days: int = 90) -> list[dict]:
    """Project one state per worker per local day (4,500 rows by default)."""
    if isinstance(start_date, str):
        start_date = date.fromisoformat(start_date)
    if days < 1:
        raise ValueError("days must be positive")
    return [
        _with_dates(state, start_date)
        for day_index in range(days)
        for state in worker_states_for_day(day_index)
    ]


def attendance_summary(states: Iterable[dict]) -> dict:
    """Count session intents separately from canonical shift references."""
    states = list(states)
    state_counts = Counter(state["attendance_state"] for state in states)
    event_counts = Counter(
        event["event_type"] for state in states for event in state["milestones"]
    )
    session_counts = {
        event_type: event_counts[event_type] for event_type in SESSION_MILESTONE_TYPES
    }
    shift_references = {
        event_type: event_counts[event_type] for event_type in SHIFT_MILESTONE_TYPES
    }
    return {
        "workers": len({state["actor_id"] for state in states}),
        "states": dict(sorted(state_counts.items())),
        "session_milestones": dict(sorted(session_counts.items())),
        "canonical_shift_milestone_references": dict(sorted(shift_references.items())),
        # Compatibility aggregate. Consumers should use the two scoped fields
        # above rather than count canonical shift events twice.
        "milestones": dict(sorted(event_counts.items())),
        "truth": PLANNING_TRUTH,
    }
