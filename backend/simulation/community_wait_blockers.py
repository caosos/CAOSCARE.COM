"""Why a ticket waited, minute by minute, over its whole wait (pure).

A department's state only changes at shift and operating-hour boundaries, so
each department's 90 days are cut into segments with a fixed set of on-site
job roles and on-call cover.  A ticket's wait ``[eligible, end)`` is split
over those segments and every minute gets exactly one blocker:

* ``waiting_for_available_staff``  - a qualified worker was on site but busy
  (or their shift ended before the job could finish);
* ``waiting_for_qualified_staff``  - someone was on site, but nobody whose
  job role may do this work (or the department should be staffed and is not);
* ``waiting_for_on_site_staff_on_call_only`` - only off-site on-call cover;
* ``waiting_for_on_call_response`` - on-call cover was called in and is on
  the way (high and urgent tickets only);
* ``waiting_for_department_opening`` - the department was closed.

The breakdown sums to the waited minutes and the dominant blocker is the
ticket's ``wait_reason``.
"""
from bisect import bisect_right
from collections import defaultdict
from functools import lru_cache

from simulation.community_coverage import OPERATING_HOURS, department_status
from simulation.community_staffing import ON_CALL, ON_SITE, _day_rota, _minutes

NO_WAIT = "none"
STAFF_BUSY = "waiting_for_available_staff"
QUALIFIED_ABSENT = "waiting_for_qualified_staff"
ON_CALL_ONLY = "waiting_for_on_site_staff_on_call_only"
ON_CALL_RESPONSE = "waiting_for_on_call_response"
DEPARTMENT_CLOSED = "waiting_for_department_opening"
# Tie-break when two blockers held a ticket for the same minutes.
BLOCKER_ORDER = (DEPARTMENT_CLOSED, ON_CALL_ONLY, ON_CALL_RESPONSE, QUALIFIED_ABSENT, STAFF_BUSY)


def duty_windows(department: str, horizon: int) -> dict[str, list[tuple[int, int, dict]]]:
    """On-site and on-call (start, end, rota row) windows in absolute minutes."""
    rows = defaultdict(list)
    for day in range(-1, horizon // 1440 + 1):
        for row in _day_rota(day):
            if row["department"] != department:
                continue
            start = day * 1440 + row["start_minute"]
            end = day * 1440 + row["end_minute"] + (1440 if row["spans_midnight"] else 0)
            rows[row["duty"]].append((start, end, row))
    return {duty: sorted(rows[duty], key=lambda item: (item[0], item[2]["actor_id"]))
            for duty in (ON_SITE, ON_CALL)}


@lru_cache(maxsize=None)
def _segments(department: str, horizon: int):
    """Sorted segment starts plus (status, on-site roles) for each segment."""
    windows = duty_windows(department, horizon)
    every = windows[ON_SITE] + windows[ON_CALL]
    marks = {0, horizon}
    for start, end, _row in every:
        marks.update(m for m in (start, end) if 0 < m < horizon)
    open_at, close_at = (_minutes(value) for value in OPERATING_HOURS[department])
    for day in range(horizon // 1440 + 1):
        marks.update(m for m in (day * 1440 + open_at, day * 1440 + close_at) if 0 < m < horizon)
    starts = sorted(marks)[:-1]
    states = []
    for at in starts:
        here = [row for start, end, row in every if start <= at < end]
        roles = frozenset(row["job_role"] for row in here if row["duty"] == ON_SITE)
        on_call = sum(row["duty"] == ON_CALL for row in here)
        states.append((department_status(department, at % 1440, len(roles), on_call), roles))
    return starts, states


def _blocker(status: str, roles_here: frozenset, eligible: tuple, called_in: bool) -> str:
    if roles_here & set(eligible):
        return STAFF_BUSY
    if called_in:  # no qualified worker on site; the on-call worker is on the way
        return ON_CALL_RESPONSE
    if roles_here:
        return QUALIFIED_ABSENT
    if status == "on_call":
        return ON_CALL_ONLY
    if status == "closed":
        return DEPARTMENT_CLOSED
    return QUALIFIED_ABSENT  # should be staffed and nobody is


def wait_breakdown(department: str, eligible: tuple, start: int, end: int, horizon: int,
                   *, called_in: bool = False) -> tuple[tuple[str, int], ...]:
    """Minutes per blocker over ``[start, end)``, in :data:`BLOCKER_ORDER`."""
    if end <= start:
        return ()
    starts, states = _segments(department, horizon)
    minutes = defaultdict(int)
    index = max(0, bisect_right(starts, start) - 1)
    at = start
    while at < end:
        segment_end = starts[index + 1] if index + 1 < len(starts) else max(end, horizon)
        status, roles_here = states[index]
        upto = min(end, segment_end)
        minutes[_blocker(status, roles_here, eligible, called_in)] += upto - at
        at, index = upto, index + 1
    return tuple((reason, minutes[reason]) for reason in BLOCKER_ORDER if minutes[reason])


def dominant(breakdown: tuple[tuple[str, int], ...]) -> str:
    """The blocker that held the ticket longest (``none`` without a wait)."""
    if not breakdown:
        return NO_WAIT
    best = max(minutes for _reason, minutes in breakdown)
    return next(reason for reason, minutes in breakdown if minutes == best)
