"""Deterministic workforce load for the living-community simulator.

This module is reference data plus pure scheduling functions.  It never
creates ``User`` records and never writes to the database.  The headcounts
and shift windows create believable simulator traffic; they are NOT
staffing, clinical, regulatory, or labor recommendations for a real facility.

Simulated workers have stable ``sim:staff:`` identities.  A shift runtime uses
these profiles to build synthetic ActorContexts and call the canonical,
receipt-backed workflow services.  Department open/closed/on-call/uncovered
status is derived in :mod:`simulation.community_coverage`.
"""
from collections import Counter, defaultdict
from functools import lru_cache
from datetime import date, datetime, time, timedelta


SIMULATION_LOAD_DISCLAIMER = (
    "Synthetic event-load fixture only; not real-world staffing or clinical coverage advice."
)
MAX_SCHEDULED_DAYS_PER_ROLLING_WEEK = 6
MIN_REST_BETWEEN_DUTIES_MINUTES = 8 * 60

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
    ("nursing", "registered_nurse", 4),
    ("nursing", "medication_reminder_support", 3),
    ("nursing", "care_aide", 15),
    ("kitchen", "cook", 3),
    ("kitchen", "dining_server", 6),
    ("kitchen", "meal_delivery_aide", 9),
    ("housekeeping", "housekeeper", 4),
    ("maintenance", "maintenance_technician", 4),
    ("transportation", "driver", 4),
    ("activities", "activities_coordinator", 4),
    ("activities", "activities_assistant", 2),
    ("front_desk", "front_desk_coordinator", 4),
    ("administration", "administration_leadership", 4),
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
    """Return all stable synthetic worker profiles in canonical order."""
    return tuple(
        _worker(department, role, number)
        for department, role, count in _HEADCOUNT
        for number in range(1, count + 1)
    )


WORKERS = build_roster()

# Owner direction (Michael, 2026-10-13): an 80-apartment, budget-constrained
# assisted-living community.  Overnight 2-3 care staff are physically present;
# med techs work 7-7 (07:00-19:00 and 19:00-07:00, Michael 2026-10-14);
# maintenance works normal hours plus after-hours ON-CALL (never on site 24 h);
# other departments keep realistic operating hours and are CLOSED otherwise.
#
# Row: (department, job role, shift, start, end, count, duty).  End <= start
# means the window crosses midnight.  ``on_site`` workers are physically
# present; ``on_call`` workers are reachable but off site and never clock in.
ON_SITE = "on_site"
ON_CALL = "on_call"
_SHIFT_LOAD = (
    ("nursing", "care_aide", "day", "06:00", "14:00", 4, ON_SITE),
    ("nursing", "registered_nurse", "day", "06:00", "14:00", 1, ON_SITE),
    ("nursing", "care_aide", "evening", "14:00", "22:00", 3, ON_SITE),
    ("nursing", "registered_nurse", "evening", "14:00", "22:00", 1, ON_SITE),
    ("nursing", "care_aide", "night", "22:00", "06:00", 2, ON_SITE),
    ("nursing", "medication_reminder_support", "med_tech_day", "07:00", "19:00", 1, ON_SITE),
    ("nursing", "medication_reminder_support", "med_tech_night", "19:00", "07:00", 1, ON_SITE),
    ("nursing", "registered_nurse", "night_on_call", "22:00", "06:00", 1, ON_CALL),
    # Service model (CO-008, owner 2026-10-15): the cook holds prep, plating and dish work;
    # dining servers serve residents in parallel at each seating.
    ("kitchen", "cook", "early", "05:30", "13:30", 1, ON_SITE),
    ("kitchen", "cook", "late", "12:00", "20:00", 1, ON_SITE),
    ("kitchen", "dining_server", "early", "06:30", "14:30", 2, ON_SITE),
    ("kitchen", "dining_server", "late", "12:00", "20:00", 2, ON_SITE),
    # Room delivery (owner estimate 2026-10-15): about 30 trays per meal need their own staff.
    ("kitchen", "meal_delivery_aide", "meals_am", "07:15", "13:15", 3, ON_SITE),
    ("kitchen", "meal_delivery_aide", "meals_pm", "16:45", "19:45", 3, ON_SITE),
    ("housekeeping", "housekeeper", "day", "08:00", "16:30", 2, ON_SITE),
    ("maintenance", "maintenance_technician", "day", "07:00", "15:30", 1, ON_SITE),
    ("maintenance", "maintenance_technician", "after_hours_on_call", "15:30", "07:00", 1, ON_CALL),
    ("transportation", "driver", "early", "07:30", "15:30", 1, ON_SITE),
    ("transportation", "driver", "late", "09:30", "17:30", 1, ON_SITE),
    ("activities", "activities_coordinator", "day", "09:00", "17:00", 1, ON_SITE),
    ("activities", "activities_coordinator", "evening", "12:00", "20:00", 1, ON_SITE),
    ("activities", "activities_assistant", "afternoon", "11:00", "19:00", 1, ON_SITE),
    ("front_desk", "front_desk_coordinator", "day", "07:00", "15:00", 1, ON_SITE),
    ("front_desk", "front_desk_coordinator", "evening", "15:00", "23:00", 1, ON_SITE),
    ("administration", "administration_leadership", "business", "08:00", "17:00", 2, ON_SITE),
)


def _pools() -> dict[tuple[str, str], tuple[dict, ...]]:
    grouped = defaultdict(list)
    for worker in WORKERS:
        grouped[(worker["department"], worker["job_role"])].append(worker)
    return {key: tuple(value) for key, value in grouped.items()}


# On-site shift names; only these have clock-in/handoff/clock-out milestones.
ON_SITE_SHIFTS = frozenset(row[2] for row in _SHIFT_LOAD if row[6] == ON_SITE)
_WORKER_POOLS = _pools()
_DAILY_NEED = Counter()
for _department, _role, _shift, _start, _end, _count, _duty in _SHIFT_LOAD:
    _DAILY_NEED[(_department, _role)] += _count


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
    """One day's duties as fresh dicts (callers may not mutate shared state)."""
    return [dict(row) for row in _day_rota(day_index)]


@lru_cache(maxsize=None)
def _day_rota(day_index: int) -> tuple[dict, ...]:
    """Build one repeatable day, including a carry-in day before day zero.

    One rotation over each role's whole daily need (on-site and on-call
    together) gives every worker at most one duty per day and spreads rest
    days evenly; the tests prove the weekly rest and between-duty rest rules.
    """
    used = Counter()
    assignments = []
    for department, role, shift, start, end, count, duty in _SHIFT_LOAD:
        pool = _WORKER_POOLS[(department, role)]
        need = _DAILY_NEED[(department, role)]
        if need > len(pool):
            raise ValueError(f"daily load exceeds roster for {department}/{role}")
        offset = (day_index * need + used[(department, role)]) % len(pool)
        for position in range(count):
            worker = pool[(offset + position) % len(pool)]
            start_minute, end_minute = _minutes(start), _minutes(end)
            assignments.append({
                "day_index": day_index,
                "shift_key": f"{department}:{shift}",
                "shift": shift,
                "start": start,
                "end": end,
                "start_minute": start_minute,
                "end_minute": end_minute,
                "spans_midnight": end_minute <= start_minute,
                "duty": duty,
                **worker,
            })
        used[(department, role)] += count
    return tuple(assignments)


def assignments_for_day(day_index: int) -> list[dict]:
    """Build one repeatable local-calendar day of duties (on site and on call).

    Rotation is deterministic and assigns a worker at most once per day.
    Overnight duties belong to the day on which they begin.
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


def _active(day_index: int, minute: int, duty: str) -> list[dict]:
    if day_index < 0:
        raise ValueError("day_index must be non-negative")
    if not 0 <= minute < 1440:
        raise ValueError("minute must be between 0 and 1439")
    absolute = day_index * 1440 + minute
    # Overnight windows begin on the prior day (-1 is the carry-in day), so a
    # run begun at midnight still shows the night staff already present.
    active = []
    for shift_day in (day_index - 1, day_index):
        for assignment in _day_rota(shift_day):
            if assignment["duty"] != duty:
                continue
            start = shift_day * 1440 + assignment["start_minute"]
            end = shift_day * 1440 + assignment["end_minute"]
            if assignment["spans_midnight"]:
                end += 1440
            if start <= absolute < end:
                active.append(dict(assignment))
    return active


def active_assignments(day_index: int, minute: int) -> list[dict]:
    """Workers physically on site at one simulated local minute."""
    return _active(day_index, minute, ON_SITE)


def on_call_assignments(day_index: int, minute: int) -> list[dict]:
    """Workers reachable on call (off site, not clocked in) at one minute."""
    return _active(day_index, minute, ON_CALL)


def worker_statuses(day_index: int, minute: int) -> list[dict]:
    """Exactly one ON DUTY / ON CALL / OFF DUTY status for each of the 50."""
    on_site = {row["actor_id"]: row for row in active_assignments(day_index, minute)}
    on_call = {row["actor_id"]: row for row in on_call_assignments(day_index, minute)}
    rows = []
    for worker in WORKERS:
        duty = on_site.get(worker["actor_id"]) or on_call.get(worker["actor_id"])
        rows.append({
            "actor_id": worker["actor_id"],
            "name": worker["name"],
            "department": worker["department"],
            "job_role": worker["job_role"],
            "status": ("on_duty" if worker["actor_id"] in on_site
                       else "on_call" if duty else "off_duty"),
            "shift": duty["shift"] if duty else None,
            "physically_present": worker["actor_id"] in on_site,
        })
    return rows
