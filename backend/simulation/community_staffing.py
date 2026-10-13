"""Deterministic workforce load for the living-community simulator.

This module is reference data plus pure scheduling functions.  It never
creates ``User`` records and never writes to the database.  The headcounts
and coverage targets create believable simulator traffic; they are NOT
staffing, clinical, regulatory, or labor recommendations for a real facility.

Simulated workers have stable ``sim:staff:`` identities.  A future shift
runtime can use these profiles to build synthetic ActorContexts and call the
canonical, receipt-backed workflow services.
"""
from collections import Counter, defaultdict
from datetime import date, datetime, time, timedelta
from typing import Iterable


SIMULATION_LOAD_DISCLAIMER = (
    "Synthetic event-load fixture only; not real-world staffing or clinical coverage advice."
)
MAX_SCHEDULED_DAYS_PER_ROLLING_WEEK = 6
MAINTENANCE_REST_TRADEOFF = (
    "The three-person maintenance pool rotates one unfilled shift each day so every "
    "synthetic technician has regular days off. Maintenance is therefore not modeled "
    "as 24-hour covered; snapshot and rota gaps are reported explicitly."
)

DEPARTMENT_LABELS = {
    "nursing": "Nursing / Care",
    "kitchen": "Dining / Kitchen",
    "housekeeping": "Housekeeping",
    "maintenance": "Maintenance",
    "transportation": "Transportation",
    "activities": "Activities",
    "front_desk": "Front Desk",
    "administration": "Administration / Leadership",
}

# (department, role, number of stable synthetic identities)
_HEADCOUNT = (
    ("nursing", "registered_nurse", 5),
    ("nursing", "medication_reminder_support", 5),
    ("nursing", "care_aide", 16),
    ("kitchen", "dining_team_member", 6),
    ("housekeeping", "housekeeper", 4),
    ("maintenance", "maintenance_technician", 3),
    ("transportation", "driver", 2),
    ("activities", "activities_coordinator", 2),
    ("front_desk", "front_desk_coordinator", 5),
    ("administration", "administration_leadership", 2),
)


def _minutes(hhmm: str) -> int:
    hour, minute = (int(part) for part in hhmm.split(":"))
    return hour * 60 + minute


def _worker(department: str, role: str, number: int) -> dict:
    role_label = role.replace("_", " ").title()
    return {
        "actor_id": f"sim:staff:{department}:{role}:{number:02d}",
        "name": f"SIM - {role_label} {number:02d}",
        "role": "staff",
        "job_role": role,
        "department": department,
        "department_label": DEPARTMENT_LABELS[department],
        "actor_type": "simulated-agent",
        "identity_basis": "synthetic",
        "simulated": True,
    }


def build_roster() -> tuple[dict, ...]:
    """Return all 50 stable synthetic worker profiles in canonical order."""
    return tuple(
        _worker(department, role, number)
        for department, role, count in _HEADCOUNT
        for number in range(1, count + 1)
    )


WORKERS = build_roster()

# Each row is one daily coverage slot.  Counts are deliberately modest load
# generators, not claims that this coverage is sufficient in a real facility.
# End <= start means the shift crosses midnight.
_SHIFT_LOAD = (
    ("nursing", "care_aide", "day", "06:00", "14:00", 5),
    ("nursing", "registered_nurse", "day", "06:00", "14:00", 1),
    ("nursing", "medication_reminder_support", "day", "06:00", "14:00", 1),
    ("nursing", "care_aide", "evening", "14:00", "22:00", 4),
    ("nursing", "registered_nurse", "evening", "14:00", "22:00", 1),
    ("nursing", "medication_reminder_support", "evening", "14:00", "22:00", 1),
    ("nursing", "care_aide", "night", "22:00", "06:00", 2),
    ("nursing", "registered_nurse", "night", "22:00", "06:00", 1),
    ("kitchen", "dining_team_member", "opening", "05:30", "13:30", 2),
    ("kitchen", "dining_team_member", "service", "10:30", "18:30", 2),
    ("housekeeping", "housekeeper", "early", "06:30", "14:30", 2),
    ("housekeeping", "housekeeper", "late", "10:30", "18:30", 1),
    ("maintenance", "maintenance_technician", "day", "07:00", "15:00", 1),
    ("maintenance", "maintenance_technician", "swing", "15:00", "23:00", 1),
    ("maintenance", "maintenance_technician", "night", "23:00", "07:00", 1),
    ("transportation", "driver", "day", "06:30", "15:00", 1),
    ("activities", "activities_coordinator", "programs", "09:00", "17:00", 1),
    ("front_desk", "front_desk_coordinator", "day", "06:00", "14:00", 1),
    ("front_desk", "front_desk_coordinator", "evening", "14:00", "22:00", 1),
    ("front_desk", "front_desk_coordinator", "night", "22:00", "06:00", 1),
    ("administration", "administration_leadership", "day", "08:00", "16:00", 1),
)


def _pools() -> dict[tuple[str, str], tuple[dict, ...]]:
    grouped = defaultdict(list)
    for worker in WORKERS:
        grouped[(worker["department"], worker["job_role"])].append(worker)
    return {key: tuple(value) for key, value in grouped.items()}


_WORKER_POOLS = _pools()
_DAILY_NEED = Counter()
for _department, _role, _shift, _start, _end, _count in _SHIFT_LOAD:
    _DAILY_NEED[(_department, _role)] += _count

# With three technicians and three non-overlapping daily slots, continuous
# maintenance coverage would schedule every identity all 90 days. The fixture
# instead rotates the uncovered slot. This is an honest simulation-load
# tradeoff, not a staffing recommendation.
_MAINTENANCE_GAP_ROTATION = ("swing", "night", "day")


def _maintenance_gap_shift(day_index: int) -> str:
    return _MAINTENANCE_GAP_ROTATION[day_index % len(_MAINTENANCE_GAP_ROTATION)]


def planned_coverage_gaps(day_index: int) -> list[dict]:
    """Return declared rota gaps; never imply coverage that was not assigned."""
    if day_index < 0:
        raise ValueError("day_index must be non-negative")
    shift = _maintenance_gap_shift(day_index)
    _, _, _, start, end, _ = next(
        row for row in _SHIFT_LOAD if row[0] == "maintenance" and row[2] == shift
    )
    return [{
        "day_index": day_index,
        "department": "maintenance",
        "shift": shift,
        "start": start,
        "end": end,
        "reason": "planned_rest_rotation",
        "truth": MAINTENANCE_REST_TRADEOFF,
    }]


def minute_in_shift(minute: int, start_minute: int, end_minute: int) -> bool:
    """Whether a minute-of-day is inside a half-open shift, including wrap."""
    if not 0 <= minute < 1440:
        raise ValueError("minute must be between 0 and 1439")
    if start_minute == end_minute:
        return True
    if end_minute > start_minute:
        return start_minute <= minute < end_minute
    return minute >= start_minute or minute < end_minute


def _assignments_for_day(day_index: int) -> list[dict]:
    """Build one repeatable day, including a carry-in day before day zero."""
    used = Counter()
    assignments = []
    for department, role, shift, start, end, count in _SHIFT_LOAD:
        pool = _WORKER_POOLS[(department, role)]
        need = _DAILY_NEED[(department, role)]
        if need > len(pool):
            raise ValueError(f"daily load exceeds roster for {department}/{role}")
        offset = (day_index * need + used[(department, role)]) % len(pool)
        for position in range(count):
            worker = pool[(offset + position) % len(pool)]
            start_minute, end_minute = _minutes(start), _minutes(end)
            if department != "maintenance" or shift != _maintenance_gap_shift(day_index):
                assignments.append({
                    "day_index": day_index,
                    "shift_key": f"{department}:{shift}",
                    "shift": shift,
                    "start": start,
                    "end": end,
                    "start_minute": start_minute,
                    "end_minute": end_minute,
                    "spans_midnight": end_minute <= start_minute,
                    **worker,
                })
        used[(department, role)] += count
    return assignments


def assignments_for_day(day_index: int) -> list[dict]:
    """Build one repeatable local-calendar day of assignments.

    Rotation is deterministic and assigns a worker at most once per day.
    Overnight assignments belong to the day on which they begin.
    """
    if day_index < 0:
        raise ValueError("day_index must be non-negative")
    return _assignments_for_day(day_index)


def _dated(assignment: dict, start_date: date) -> dict:
    shift_date = start_date + timedelta(days=assignment["day_index"])
    starts_at = datetime.combine(shift_date, time.min) + timedelta(minutes=assignment["start_minute"])
    ends_at = datetime.combine(shift_date, time.min) + timedelta(minutes=assignment["end_minute"])
    if assignment["spans_midnight"]:
        ends_at += timedelta(days=1)
    return {**assignment, "date": shift_date.isoformat(),
            "starts_at": starts_at.isoformat(), "ends_at": ends_at.isoformat()}


def project_schedule(start_date: date | str, days: int = 90) -> list[dict]:
    """Return a deterministic local-clock projection (90 days by default)."""
    if isinstance(start_date, str):
        start_date = date.fromisoformat(start_date)
    if days < 1:
        raise ValueError("days must be positive")
    return [
        _dated(assignment, start_date)
        for day_index in range(days)
        for assignment in assignments_for_day(day_index)
    ]


def active_assignments(day_index: int, minute: int) -> list[dict]:
    """Return workers on shift at one simulated local minute.

    Includes prior-day assignments whose shift crosses midnight.
    """
    if day_index < 0:
        raise ValueError("day_index must be non-negative")
    if not 0 <= minute < 1440:
        raise ValueError("minute must be between 0 and 1439")
    absolute = day_index * 1440 + minute
    # At the beginning of a projection, night coverage started on the
    # carry-in day (-1); otherwise a 90-day run begun at midnight would
    # incorrectly show no nurse/front-desk/maintenance presence until dawn.
    days = (day_index - 1, day_index)
    active = []
    for shift_day in days:
        for assignment in _assignments_for_day(shift_day):
            start = shift_day * 1440 + assignment["start_minute"]
            end = shift_day * 1440 + assignment["end_minute"]
            if assignment["spans_midnight"]:
                end += 1440
            if start <= absolute < end:
                active.append(assignment)
    return active


def coverage_summary(day_index: int, minute: int, departments: Iterable[str] = DEPARTMENT_LABELS) -> dict:
    """Summarize on-shift synthetic coverage and name uncovered departments."""
    wanted = tuple(departments)
    unknown = set(wanted) - set(DEPARTMENT_LABELS)
    if unknown:
        raise ValueError(f"unknown departments: {', '.join(sorted(unknown))}")
    by_department = {department: [] for department in wanted}
    for assignment in active_assignments(day_index, minute):
        if assignment["department"] in by_department:
            by_department[assignment["department"]].append(assignment)
    coverage = {
        department: {
            "label": DEPARTMENT_LABELS[department],
            "on_shift": len(rows),
            "actor_ids": [row["actor_id"] for row in rows],
            "job_roles": sorted({row["job_role"] for row in rows}),
        }
        for department, rows in by_department.items()
    }
    return {
        "day_index": day_index,
        "minute": minute,
        "coverage": coverage,
        "gaps": [department for department, item in coverage.items() if item["on_shift"] == 0],
        "planned_rota_gaps": planned_coverage_gaps(day_index),
        "coverage_tradeoffs": [MAINTENANCE_REST_TRADEOFF],
        "disclaimer": SIMULATION_LOAD_DISCLAIMER,
    }
