"""Who a simulated escalation reaches, from the roster at one simulated minute.

Reads only :func:`simulation.community_staffing.worker_statuses` and
:func:`simulation.community_staffing.active_assignments`; never invents a
worker.  When nobody suitable is on duty or on call the answer is ``None``
and the caller records "no lead reachable" - it is never filled in.

Simulation assumption (not a real facility's chain of command):

* level 1 - the ticket's department lead: for Nursing the registered nurse,
  otherwise any worker of that department; on site first, then on call;
* level 2 - the supervisor: the Executive Director, else the Administrator on site, else the
  registered nurse on site, else the registered nurse on call.
"""
from typing import Optional

from simulation.community_staffing import active_assignments, worker_statuses

_LEAD_ROLES = {"nursing": ("registered_nurse",)}
_SUPERVISOR_CHAIN = (
    ("administration", "executive_director", ("on_duty",)),
    ("administration", "administrator", ("on_duty",)),
    ("nursing", "registered_nurse", ("on_duty",)),
    ("nursing", "registered_nurse", ("on_call",)),
)
_REACHABLE = ("on_duty", "on_call")


def _pick(rows: list[dict], department: str, roles: Optional[tuple], statuses: tuple) -> Optional[dict]:
    for status in statuses:
        matches = sorted(
            (row for row in rows
             if row["department"] == department and row["status"] == status
             and (roles is None or row["job_role"] in roles)),
            key=lambda row: row["actor_id"],
        )
        if matches:
            return matches[0]
    return None


def lead_for(level: int, department: str, absolute_minute: int) -> Optional[dict]:
    """The reachable lead for one escalation level, or None (truthfully)."""
    day_index, minute = divmod(absolute_minute, 1440)
    rows = worker_statuses(day_index, minute)
    if level == 1:
        chosen = _pick(rows, department, _LEAD_ROLES.get(department), _REACHABLE)
    else:
        chosen = next((
            row for dept, role, statuses in _SUPERVISOR_CHAIN
            if (row := _pick(rows, dept, (role,), statuses)) is not None
        ), None)
    if chosen is None:
        return None
    return {key: chosen[key] for key in (
        "actor_id", "name", "department", "job_role", "status", "shift", "physically_present",
    )}


def _present(department: str, absolute_minute: int) -> list[dict]:
    if absolute_minute < 0:
        return []
    day_index, minute = divmod(absolute_minute, 1440)
    return [row for row in active_assignments(day_index, minute) if row["department"] == department]


def on_site_since(department: str, absolute_minute: int) -> Optional[int]:
    """Start of the department's current unbroken on-site period, or None.

    Overlapping shifts chain together (kitchen early 05:30 + late 12:00 is
    one period from 05:30).  None means nobody of that department is on site.
    """
    present = _present(department, absolute_minute)
    if not present:
        return None
    since = absolute_minute
    for _ in range(16):  # a department chains only a few shifts per day
        start = min(row["day_index"] * 1440 + row["start_minute"] for row in present)
        if start >= since:
            break
        since = start
        present = _present(department, since - 1)
        if not present:
            break
    return since
