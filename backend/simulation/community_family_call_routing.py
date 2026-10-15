"""Who coordinates a family-call request, by time of day (owner rule 2026-10-14).

* Administration during its hours (before 17:00) when it can finish the
  request before it closes; otherwise the Front Desk, which is open;
* Front Desk from 17:00 to 23:00;
* otherwise the routine request is queued for the next staffed period
  (Administration's next opening, enforced by coverage-gated dispatch);
* urgent resident-care needs go to the on-duty care team (Nursing).

Coordination only: routing never claims a call was placed or a provider
notified.  The windows are configuration; change them here only.
"""
from simulation.community_coverage import OPERATING_HOURS, opens_on
from simulation.community_staffing import _minutes, minute_in_shift
from simulation.community_ticket_plan import CLAIM_TO_COMPLETE_MINUTES, OPEN_TO_CLAIM_MINUTES


FAMILY_CALL_ROUTING = (
    ("administration", OPERATING_HOURS["administration"][0], "17:00"),
    ("front_desk", "17:00", "23:00"),
)
QUEUE_DEPARTMENT = "administration"
URGENT_DEPARTMENT = "nursing"
TICKET_SPAN_MINUTES = OPEN_TO_CLAIM_MINUTES + CLAIM_TO_COMPLETE_MINUTES


def family_call_department(minute: int, *, day_index: int = 0, urgent: bool = False) -> str:
    """Department that owns a family-call request raised at ``minute`` of ``day_index``.

    Administration works business days only; on its closed days the Front Desk
    coordinates during its hours, and later requests queue for the Front Desk.
    """
    if urgent:
        return URGENT_DEPARTMENT
    if not opens_on(QUEUE_DEPARTMENT, day_index):
        return "front_desk"
    for department, start, end in FAMILY_CALL_ROUTING:
        start_minute, end_minute = _minutes(start), _minutes(end)
        finish = (minute + TICKET_SPAN_MINUTES) % 1440
        if (minute_in_shift(minute, start_minute, end_minute)
                and minute_in_shift(finish, start_minute, end_minute)):
            return department
    # Raised too late for one window but inside the next one's opening hours.
    for department, start, end in FAMILY_CALL_ROUTING[1:]:
        if minute_in_shift(minute, _minutes(OPERATING_HOURS[department][0]), _minutes(end)):
            return department
    return QUEUE_DEPARTMENT
