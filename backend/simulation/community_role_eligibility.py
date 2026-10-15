"""Which job roles may take each routine, in preference order (one source of truth).

The capacity scheduler (:mod:`simulation.community_capacity_schedule`) offers
a ticket only to on-site workers whose ``job_role`` is listed for its routine,
preferring earlier roles: a medication reminder goes to the med tech, then the
RN, and never to a care aide; hands-on care goes to care aides first, then the
med tech, the RN last.  A ticket with no qualified worker on site waits, with
that reason recorded; it is never given to an unqualified worker.

Departments with one job role need no row: every routine of that department
goes to that role.  Nursing has three roles, so every nursing routine must be
listed here, and an unlisted one is refused rather than guessed.  This is a
simulation assumption about scope of work, not a clinical or labor rule.
"""
from simulation.community_staffing import WORKERS

MED_TECH = "medication_reminder_support"
RN = "registered_nurse"
CARE_AIDE = "care_aide"

_MEDICATION = (MED_TECH, RN)
_HANDS_ON_CARE = (CARE_AIDE, MED_TECH, RN)

_NURSING_ROUTINES = {
    "morning_medication_reminder": _MEDICATION,
    "evening_medication_reminder": _MEDICATION,
    "shower_assistance": _HANDS_ON_CARE,
    "toileting_transfer_support": _HANDS_ON_CARE,
    "afternoon_toileting_transfer_support": _HANDS_ON_CARE,
    "evening_toileting_transfer_support": _HANDS_ON_CARE,
    "overnight_room_check": _HANDS_ON_CARE,
    "morning_room_check": _HANDS_ON_CARE,
    "night_room_check": _HANDS_ON_CARE,
    "resident_call_help_up": _HANDS_ON_CARE,
    "resident_call_bathroom": _HANDS_ON_CARE,
    "resident_call_dressing": _HANDS_ON_CARE,
    "resident_call_reposition": _HANDS_ON_CARE,
    # A "please check on me" call is answered by care staff first; the
    # simulator records no clinical assessment either way.
    "resident_call_check_on_me": _HANDS_ON_CARE,
    "staff_report_activity_help": _HANDS_ON_CARE,
}


def _department_roles() -> dict[str, tuple[str, ...]]:
    roles: dict[str, list[str]] = {}
    for worker in WORKERS:
        roles.setdefault(worker["department"], [])
        if worker["job_role"] not in roles[worker["department"]]:
            roles[worker["department"]].append(worker["job_role"])
    return {department: tuple(names) for department, names in roles.items()}


DEPARTMENT_ROLES = _department_roles()
ROUTINE_ROLES = {("nursing", routine): roles for routine, roles in _NURSING_ROUTINES.items()}

for (_department, _routine), _roles in ROUTINE_ROLES.items():
    _unknown = set(_roles) - set(DEPARTMENT_ROLES[_department])
    if _unknown:
        raise ValueError(f"{_routine}: roles not on the {_department} roster: {sorted(_unknown)}")


class RoleEligibilityError(ValueError):
    """A routine has no declared qualified roles."""


def eligible_roles(department: str, routine: str) -> tuple[str, ...]:
    """Qualified job roles for one routine, most preferred first."""
    if (department, routine) in ROUTINE_ROLES:
        return ROUTINE_ROLES[(department, routine)]
    roles = DEPARTMENT_ROLES.get(department)
    if roles is None:
        raise RoleEligibilityError(f"unknown department: {department}")
    if len(roles) != 1:
        raise RoleEligibilityError(f"{department} routine {routine!r} has no declared eligible roles")
    return roles


def role_rank(roles: tuple[str, ...], job_role: str):
    """Preference position of ``job_role`` (None when not qualified)."""
    return roles.index(job_role) if job_role in roles else None
