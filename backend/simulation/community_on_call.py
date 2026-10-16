"""Calling in on-call cover for high and urgent work (pure planning).

When a department has no qualified worker on site - maintenance after 15:30,
or a role that is only on call overnight - a high or urgent ticket calls in
the on-call worker of a qualified role.  That worker is off site, so they
claim the ticket only after a response delay; until that claim they are
never shown as physically present.  Normal and low priority work keeps
waiting for on-site hours.

Response delays are simulation assumptions, not measured facility data: a
maintenance technician driving in from home (40 simulated minutes) and an RN
on call (30 minutes).  A worker already on site from a previous call-in
takes the next urgent ticket without a new delay.
"""
from typing import Optional

CALL_IN_PRIORITIES = frozenset({"urgent", "high"})
CALL_IN_RESPONSE_MINUTES = {"maintenance": 40, "nursing": 30}
DEFAULT_CALL_IN_RESPONSE_MINUTES = 40


def response_minutes(department: str) -> int:
    return CALL_IN_RESPONSE_MINUTES.get(department, DEFAULT_CALL_IN_RESPONSE_MINUTES)


def call_in(*, department: str, priority: str, eligible: tuple, at: int, work: int,
            horizon: int, on_call_rows: list, busy_until: dict, on_site_until: dict,
            next_on_site_start: Optional[int]) -> Optional[tuple[int, dict]]:
    """(claim minute, worker) for the on-call worker to call in, or None.

    ``on_call_rows`` are the department's (start, end, row) on-call windows
    active at ``at``.  The worker must be free, qualified, still on call for
    the whole job, and able to arrive before a qualified on-site shift starts
    (otherwise the arriving shift takes the ticket).
    """
    if priority not in CALL_IN_PRIORITIES:
        return None
    for _start, end, row in sorted(on_call_rows, key=lambda item: (
            eligible.index(item[2]["job_role"]) if item[2]["job_role"] in eligible else len(eligible),
            item[2]["actor_id"])):
        actor = row["actor_id"]
        if row["job_role"] not in eligible or busy_until.get(actor, 0) > at:
            continue
        claim = at if on_site_until.get(actor, -1) >= at else at + response_minutes(department)
        if claim + work > end or claim + work >= horizon:
            continue
        if next_on_site_start is not None and claim >= next_on_site_start:
            continue
        return claim, row
    return None
