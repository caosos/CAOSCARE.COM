"""Time-bound work: a meal or activity not claimed in its window is not served.

Dinner offered at breakfast time the next morning is not dinner.  Each
time-bound routine has one service window, closing at a minute of the day the
ticket was requested.  A ticket still unclaimed when its window closes gets a
truthful terminal state: the department lead on site closes it as *not
served* through the canonical lifecycle (a receipted ``skipped`` task), and
the executor records that as an ``expire`` phase.

Resident calls and care needs (toileting, showers, checks, reminders) are
deliberately absent: they never expire and wait until someone does them.
Window ends are simulation assumptions, chosen inside each department's
staffed hours so a lead is on site to close the service.
"""
from typing import Optional

from simulation.community_staffing import _minutes

# routine -> service window end, local time of the request's day.  Breakfast
# and lunch are not time-bound yet (owner decision pending; the CO-008
# plan-realism report measures the effect of adding them).
SERVICE_WINDOW_ENDS = {
    "dinner": "19:30",
    "activity_offer_and_escort": "18:00",
}
NOT_SERVED = "not_served_service_window_closed"


def service_deadline(routine: str, requested_at: int) -> Optional[int]:
    """Absolute minute the routine's window closes, or None when it never expires."""
    end = SERVICE_WINDOW_ENDS.get(routine)
    if end is None:
        return None
    return (requested_at // 1440) * 1440 + _minutes(end)


def department_lead(on_site_rows: list) -> Optional[dict]:
    """The on-site worker who closes a missed service: longest on shift, then id."""
    if not on_site_rows:
        return None
    return min(on_site_rows, key=lambda item: (item[0], item[2]["actor_id"]))[2]


def window_label(routine: str) -> str:
    return f"{routine.replace('_', ' ')} service window (closes {SERVICE_WINDOW_ENDS[routine]})"
