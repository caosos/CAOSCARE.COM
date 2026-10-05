"""SIM-3: who fills a simulated staff role, and what the canonical record
already shows was done.

A staff role in a run is filled one of three ways (`cast[role].filled_by`):
  simulated   the run's simulated actor acts (SIM-1 behaviour)
  real        a real, signed-in user holds the role. The simulator never acts
              for them: their work happens through the normal staff UI and
              routes, with their own authenticated receipts
  unassigned  nobody holds the role; the work waits

The scheduler does not track work separately. Before each staff step it
reads the canonical task: if the step's outcome is already there (whoever
did it), the step is observed and the run moves on, citing the receipt that
recorded it. Otherwise only a simulated holder acts; a real or empty role
waits, and nothing is recorded on its behalf.
"""
from typing import Optional

from deps import db
from routes.staff_scope import ADMIN_ROLES, acts_for, members_query

MODES = ("simulated", "real", "unassigned")
STAFF_ROLES = ("owner", "admin", "staff", "front_desk")

# The canonical receipts that can satisfy a step, earliest first.
_SATISFIED_BY = {
    "acknowledge": ("task_acknowledged", "task_assigned", "task_in_progress", "task_completed", "task_cancelled"),
    "start": ("task_in_progress", "task_completed", "task_cancelled"),
    "note": ("task_note_added", "task_completed", "task_cancelled"),
    "complete": ("task_completed", "task_cancelled"),
}


class StaffingError(Exception):
    pass


def is_simulated_id(user_id: str) -> bool:
    """Simulated actor ids carry the `sim:` prefix (roster.py); no real
    account may stand in for one."""
    return user_id.startswith("sim:")


def fill_of(cast: dict, role_key: str) -> dict:
    """The role's holder; a role with no record of a holder is simulated."""
    return (cast.get(role_key) or {}).get("filled_by") or {"mode": "simulated"}


def step_satisfied(step: dict, task: Optional[dict]) -> bool:
    """Whether the canonical task already shows this step's outcome."""
    if not task or step["action"] not in _SATISFIED_BY:
        return False
    closed = task.get("status") in ("completed", "skipped")
    action = step["action"]
    if action == "acknowledge":
        return closed or bool(task.get("acknowledged_at") or task.get("assigned_to")) or task.get("status") == "in_progress"
    if action == "start":
        return closed or task.get("status") == "in_progress"
    if action == "note":
        return closed or any(e.get("field") == "note" for e in task.get("event_log") or [])
    return closed


async def satisfying_receipt(step: dict, task_id: str) -> Optional[dict]:
    """The earliest canonical receipt on the task that records this step."""
    return await db.receipts.find_one(
        {"related_object_type": "task", "related_object_id": task_id,
         "action_type": {"$in": list(_SATISFIED_BY[step["action"]])}},
        {"_id": 0}, sort=[("created_at", 1)])


async def resolve_holder(role: dict, mode: str, user_id: Optional[str]) -> dict:
    """Validate a new holder for a role. A real holder must be an existing
    staff user who acts for the role's department; never a simulated id."""
    if mode not in MODES:
        raise StaffingError(f"Unknown mode {mode}; use one of {', '.join(MODES)}")
    if mode != "real":
        return {"mode": mode}
    if not user_id or is_simulated_id(user_id):
        raise StaffingError("A real holder needs the user_id of a real staff account")
    user = await db.users.find_one({"user_id": user_id}, {"_id": 0, "password_hash": 0})
    if not user or user.get("role") not in STAFF_ROLES:
        raise StaffingError(f"No staff account {user_id}")
    if not acts_for(user, role.get("department")):
        raise StaffingError(f"{user.get('name') or user_id} does not act for {role.get('department')}")
    return {"mode": "real", "user_id": user_id, "name": user.get("name"), "user_role": user.get("role")}


async def candidates(role: dict) -> list:
    """Real staff who may hold the role: department members and admins."""
    dept = role.get("department")
    q = {"$or": [members_query(dept), {"role": {"$in": list(ADMIN_ROLES)}}]}
    users = await db.users.find(q, {"_id": 0, "user_id": 1, "name": 1, "role": 1, "department": 1}).sort(
        "name", 1).to_list(200)
    return [u for u in users if not is_simulated_id(u["user_id"]) and acts_for(u, dept)]
