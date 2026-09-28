"""Which departments a signed-in user acts for - the one rule behind claim,
assign and the assignable roster for department requests.

- owner / admin: every department (checked by `acts_for`).
- staff: their own department.
- front_desk: the Administration department (front-desk and complaint
  requests route there - resident_requests.CATEGORY_ALIASES), plus their own
  department if one is set.

Mirrored for display in frontend/src/lib/maintenance.js (actingDepartments);
the backend check here is the authority.
"""
from typing import Optional

ADMIN_ROLES = ("owner", "admin")
FRONT_DESK_DEPARTMENT = "administration"


def acting_departments(user: Optional[dict]) -> set:
    if not user:
        return set()
    depts = set()
    if user.get("role") in ("staff", "front_desk") and user.get("department"):
        depts.add(user["department"])
    if user.get("role") == "front_desk":
        depts.add(FRONT_DESK_DEPARTMENT)
    return depts


def acts_for(user: Optional[dict], department: Optional[str]) -> bool:
    if (user or {}).get("role") in ADMIN_ROLES:
        return True
    return bool(department) and department in acting_departments(user)


def members_query(department: str) -> dict:
    """Mongo filter for the people who act for `department`."""
    q: dict = {"department": department}
    if department == FRONT_DESK_DEPARTMENT:
        q = {"$or": [q, {"role": "front_desk"}]}
    return q
