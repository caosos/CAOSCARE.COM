"""Truthful department status for the living-community staffing plan.

Pure functions over :mod:`simulation.community_staffing`; no database, User
records, or execution.  A department is, at one simulated minute:

* ``on_duty``   - at least one worker is physically on site;
* ``on_call``   - outside operating hours, a worker is reachable off site;
* ``closed``    - outside operating hours with no on-call arrangement;
* ``uncovered`` - it should be staffed (operating hours, or its configured
  on-call window) and nobody is.  Only this state is a coverage gap.
"""
from typing import Iterable

from simulation.community_staffing import (
    DEPARTMENT_LABELS,
    SIMULATION_LOAD_DISCLAIMER,
    ON_CALL as ON_CALL_DUTY,
    ON_SITE,
    _assignments_for_day,
    _minutes,
    active_assignments,
    minute_in_shift,
    on_call_assignments,
)


ON_DUTY, ON_CALL, CLOSED, UNCOVERED = "on_duty", "on_call", "closed", "uncovered"
DEPARTMENT_STATUSES = (ON_DUTY, ON_CALL, CLOSED, UNCOVERED)

# Operating hours (start, end; equal means 24 h) and whether after-hours
# on-call cover is part of the department's model (owner direction 2026-10-13).
OPERATING_HOURS = {
    "nursing": ("00:00", "00:00"),
    "kitchen": ("05:30", "20:00"),
    "housekeeping": ("08:00", "16:30"),
    "maintenance": ("07:00", "15:30"),
    "transportation": ("07:30", "17:30"),
    "activities": ("09:00", "20:00"),
    "front_desk": ("07:00", "23:00"),
    "administration": ("08:00", "17:00"),
}
AFTER_HOURS_ON_CALL = frozenset({"maintenance"})


def is_open(department: str, minute: int) -> bool:
    start, end = OPERATING_HOURS[department]
    return minute_in_shift(minute, _minutes(start), _minutes(end))


def department_status(department: str, minute: int, on_site: int, on_call: int) -> str:
    """Classify one department from its hours and who is actually there."""
    if department not in DEPARTMENT_LABELS:
        raise ValueError(f"unknown department: {department}")
    if on_site > 0:
        return ON_DUTY
    if is_open(department, minute):
        return UNCOVERED
    if on_call > 0:
        return ON_CALL
    return UNCOVERED if department in AFTER_HOURS_ON_CALL else CLOSED


def coverage_summary(day_index: int, minute: int,
                     departments: Iterable[str] = DEPARTMENT_LABELS) -> dict:
    """Per-department status with on-site and on-call workers named."""
    wanted = tuple(departments)
    unknown = set(wanted) - set(DEPARTMENT_LABELS)
    if unknown:
        raise ValueError(f"unknown departments: {', '.join(sorted(unknown))}")
    on_site = active_assignments(day_index, minute)
    on_call = on_call_assignments(day_index, minute)
    coverage = {}
    for department in wanted:
        here = [row for row in on_site if row["department"] == department]
        reachable = [row for row in on_call if row["department"] == department]
        start, end = OPERATING_HOURS[department]
        coverage[department] = {
            "label": DEPARTMENT_LABELS[department],
            "status": department_status(department, minute, len(here), len(reachable)),
            "on_shift": len(here),
            "actor_ids": [row["actor_id"] for row in here],
            "job_roles": sorted({row["job_role"] for row in here}),
            "on_call": len(reachable),
            "on_call_actor_ids": [row["actor_id"] for row in reachable],
            "operating_hours": "24 hours" if start == end else f"{start}-{end}",
        }
    return {
        "day_index": day_index,
        "minute": minute,
        "coverage": coverage,
        "gaps": [key for key, item in coverage.items() if item["status"] == UNCOVERED],
        "planned_rota_gaps": planned_coverage_gaps(day_index),
        "coverage_tradeoffs": [],
        "disclaimer": SIMULATION_LOAD_DISCLAIMER,
    }


def _windows(day_index: int) -> list[tuple[int, int, str, str]]:
    """(start, end, department, duty) relative to ``day_index`` midnight."""
    rows = []
    for shift_day in (day_index - 1, day_index):
        # Day -1 is the deterministic carry-in day (same rule as active_assignments).
        for row in _assignments_for_day(shift_day):
            start = (shift_day - day_index) * 1440 + row["start_minute"]
            end = (shift_day - day_index) * 1440 + row["end_minute"]
            if row["spans_midnight"]:
                end += 1440
            rows.append((start, end, row["department"], row["duty"]))
    return rows


def planned_coverage_gaps(day_index: int) -> list[dict]:
    """Every UNCOVERED window in one day, evaluated at each status boundary."""
    if day_index < 0:
        raise ValueError("day_index must be non-negative")
    windows = _windows(day_index)
    boundaries = {0, 1440}
    for start, end, _department, _duty in windows:
        boundaries.update(m for m in (start, end) if 0 < m < 1440)
    for start, end in OPERATING_HOURS.values():
        boundaries.update(m for m in (_minutes(start), _minutes(end)) if 0 < m < 1440)
    ordered = sorted(boundaries)
    gaps = []
    for segment_start, segment_end in zip(ordered, ordered[1:]):
        for department in DEPARTMENT_LABELS:
            here = [w for w in windows if w[2] == department and w[0] <= segment_start < w[1]]
            status = department_status(
                department, segment_start,
                sum(w[3] == ON_SITE for w in here), sum(w[3] == ON_CALL_DUTY for w in here),
            )
            if status != UNCOVERED:
                continue
            if gaps and gaps[-1]["department"] == department and gaps[-1]["end_minute"] == segment_start:
                gaps[-1]["end_minute"] = segment_end
                gaps[-1]["uncovered_minutes"] = segment_end - gaps[-1]["start_minute"]
                continue
            gaps.append({
                "day_index": day_index, "department": department,
                "start_minute": segment_start, "end_minute": segment_end,
                "uncovered_minutes": segment_end - segment_start,
                "reason": "derived_from_planned_assignments",
            })
    return sorted(gaps, key=lambda gap: (gap["start_minute"], gap["department"]))
