"""Read-only composition for the living-community simulator foundation.

This module joins the static community, workforce, and routine recipes for the
admin UI.  It does not provision residents, start a run, or write operational
records.  The response therefore says ``planning_only`` explicitly.
"""
from collections import Counter
from dataclasses import asdict

from simulation.community_blueprint import (
    BURN_IN_RESIDENTS,
    COMMUNITY_ID,
    OCCUPIED_APARTMENT_TARGET,
    RESIDENT_TARGET,
    SUMMARY,
)
from simulation.community_routines import (
    ADAPTER_CAPABILITIES,
    BLOCKED,
    plan_first_24_hours,
)
from simulation.community_outcomes import plan_routine_outcomes
from simulation.community_staffing import (
    DEPARTMENT_LABELS,
    SIMULATION_LOAD_DISCLAIMER,
    WORKERS,
    active_assignments,
    assignments_for_day,
    coverage_summary,
)
from simulation.community_shift_events import event_counts, planned_events_for_day
from simulation.community_attendance import attendance_summary, worker_states_for_day


def _department_rows(day_index: int, minute: int) -> list[dict]:
    worker_counts = Counter(worker["department"] for worker in WORKERS)
    assignments = assignments_for_day(day_index)
    shift_names = {
        department: {
            row["shift"] for row in assignments if row["department"] == department
        }
        for department in DEPARTMENT_LABELS
    }
    snapshot = coverage_summary(day_index, minute)
    coverage_24h = {
        department: all(
            any(
                row["department"] == department
                for row in active_assignments(day_index, check_minute)
            )
            for check_minute in range(1440)
        )
        for department in DEPARTMENT_LABELS
    }
    return [
        {
            "slug": department,
            "label": label,
            "worker_count": worker_counts[department],
            "shift_count": len(shift_names[department]),
            "on_shift_now": snapshot["coverage"][department]["on_shift"],
            "coverage_24h": coverage_24h[department],
        }
        for department, label in DEPARTMENT_LABELS.items()
    ]


def _capability_rows(status: str) -> list[dict]:
    return [
        {"id": key, "name": key.replace("_", " ").title(), **details}
        for key, details in ADAPTER_CAPABILITIES.items()
        if details["status"] == status
    ]


def community_overview(day_index: int = 0, minute: int = 0) -> dict:
    """Return declared scale and plan facts without implying execution."""
    if not 0 <= day_index < 90:
        raise ValueError("day_index must be between 0 and 89")
    if not 0 <= minute < 1440:
        raise ValueError("minute must be between 0 and 1439")

    events = plan_first_24_hours(day_index=day_index)
    outcomes = plan_routine_outcomes(events)
    outcome_counts = Counter(outcome.planned_disposition for outcome in outcomes)
    shift_events = planned_events_for_day(day_index)
    attendance = worker_states_for_day(day_index)
    attendance_counts = attendance_summary(attendance)
    blocked_intents = sum(event.blocked_adapter is not None for event in events)
    return {
        "community_id": COMMUNITY_ID,
        "execution_status": "planning_only",
        "truth_statement": (
            "This is a deterministic preview. Residents and shifts are not yet "
            "provisioned, clocked in, or executing autonomous work."
        ),
        "residents": {
            "count": len(BURN_IN_RESIDENTS),
            "burn_in_target": len(BURN_IN_RESIDENTS),
            "target": RESIDENT_TARGET,
        },
        "apartments": {
            "total": SUMMARY["apartments"],
            "occupied": SUMMARY["occupied_apartments"],
            "occupancy_target": OCCUPIED_APARTMENT_TARGET,
        },
        "workers": {"count": len(WORKERS), "simulated": True},
        "worker_attendance": {
            **attendance_counts["states"],
            **attendance_counts["session_milestones"],
            "canonical_shift_events_reported_under": "shift_events",
            "executed": 0,
            "truth": attendance_counts["truth"],
        },
        "shift_events": {**event_counts(shift_events), "executed": 0},
        "departments": _department_rows(day_index, minute),
        "routines": {
            "planned": len(events),
            "planned_completed": outcome_counts["completed"],
            "planned_refused": outcome_counts["resident_refused"],
            "planned_rescheduled": outcome_counts["resident_requested_reschedule"],
            "provider_boundaries": blocked_intents,
            "executed": 0,
        },
        "blocked_capabilities": _capability_rows(BLOCKED),
        "unsafe_capabilities": [
            {
                "id": "medication_administration",
                "name": "Medication administration or adherence claims",
                "reason": "The simulator plans reminders only.",
            },
            {
                "id": "external_provider_effects",
                "name": "External calls, bookings, alerts, and publishing",
                "reason": "Provider-facing adapters remain disabled until simulation-isolated.",
            },
        ],
        "coverage_disclaimer": SIMULATION_LOAD_DISCLAIMER,
        "day_index": day_index,
        "minute": minute,
    }


def community_preview(day_index: int = 0, minute: int = 0) -> dict:
    """Return the first-day recipe for inspection; never dispatch it."""
    overview = community_overview(day_index, minute)
    source_events = plan_first_24_hours(day_index=day_index)
    events = []
    for event in source_events:
        row = asdict(event)
        row["time"] = event.time_hhmm
        row["adapter_status"] = event.adapter_status
        events.append(row)
    outcomes = []
    for outcome in plan_routine_outcomes(source_events):
        row = asdict(outcome)
        row["planned_resolution_time"] = outcome.planned_resolution_hhmm
        row["rescheduled_to_time"] = outcome.rescheduled_to_hhmm
        outcomes.append(row)
    return {
        "overview": overview,
        "resident_keys": [resident.resident_key for resident in BURN_IN_RESIDENTS],
        "shift_assignments": assignments_for_day(day_index),
        "worker_attendance": worker_states_for_day(day_index),
        "planned_shift_events": planned_events_for_day(day_index),
        "routine_events": events,
        "planned_outcomes": outcomes,
    }
