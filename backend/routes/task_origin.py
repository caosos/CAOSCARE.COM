"""Where a StaffTask came from, and whether it is live or simulated - one rule.

Issue #153: a count of "completed today" mixed simulator routine work, test
records and real resident requests into one number. Every dashboard tile and
its drill-down classify tasks with the filters below, so a tile's number and
the rows behind it can never disagree.

Kinds are tried in order; a task gets the first kind it matches:
  scheduled_routine  - planned care/service (a template occurrence, or a
                       simulator routine event "simulator:event:...")
  resident_request   - raised for a resident through the request bus
                       (Aria voice, room-screen button, front desk on the
                       resident's behalf, a simulated resident)
  staff_generated    - created by staff, admin Aria, or the system
  unknown            - anything else (stated, never guessed)

World: simulated if the record says so (simulated flag, simulation run id or
source "simulator"); otherwise live. A live record is not proof of a real
resident - TEST/MOCK data without a marker stays "live" and is shown as it is.
"""
from models import RESIDENT_ORIGIN_SOURCES

KINDS = ("scheduled_routine", "resident_request", "staff_generated", "unknown")

KIND_LABELS = {
    "scheduled_routine": "Scheduled routine",
    "resident_request": "Resident request",
    "staff_generated": "Staff / system created",
    "unknown": "Origin not recorded",
}

KIND_BASIS = {
    "scheduled_routine": "has a schedule template, or is a simulator routine event",
    "resident_request": f"source is one of {', '.join(RESIDENT_ORIGIN_SOURCES)}",
    "staff_generated": "source is staff, system or admin Aria",
    "unknown": "no recognised origin on the record",
}

_RULES = {
    "scheduled_routine": {"$or": [{"template_id": {"$nin": [None, ""]}},
                                  {"conversation_session_id": {"$regex": "^simulator:event:"}}]},
    "resident_request": {"source": {"$in": list(RESIDENT_ORIGIN_SOURCES)}},
    "staff_generated": {"source": {"$in": ["staff", "system", "aria_admin"]}},
}

SIMULATED = {"$or": [{"simulated": True}, {"simulation_run_id": {"$nin": [None, ""]}}, {"source": "simulator"}]}
LIVE = {"$nor": SIMULATED["$or"]}


def kind_filter(kind: str) -> dict:
    """Mongo filter selecting exactly the tasks of this kind."""
    if kind not in KINDS:
        raise ValueError(f"unknown origin kind {kind}")
    earlier = [_RULES[k] for k in KINDS[:KINDS.index(kind)]]
    own = _RULES.get(kind)
    parts = ([{"$nor": earlier}] if earlier else []) + ([own] if own else [])
    return {"$and": parts} if len(parts) > 1 else parts[0]


def world_filter(world: str) -> dict:
    if world == "simulated":
        return SIMULATED
    if world == "live":
        return LIVE
    raise ValueError(f"unknown world {world}")


def kind_of(task: dict) -> str:
    """Python form of the same rule, for one already-loaded task."""
    sess = task.get("conversation_session_id") or ""
    if task.get("template_id") or sess.startswith("simulator:event:"):
        return "scheduled_routine"
    if task.get("source") in RESIDENT_ORIGIN_SOURCES:
        return "resident_request"
    if task.get("source") in ("staff", "system", "aria_admin"):
        return "staff_generated"
    return "unknown"


def world_of(task: dict) -> str:
    sim = task.get("simulated") is True or task.get("simulation_run_id") or task.get("source") == "simulator"
    return "simulated" if sim else "live"


def routine_name(task: dict):
    """The routine (e.g. morning_medication_reminder) of a simulator routine event."""
    sess = task.get("conversation_session_id") or ""
    return sess.rsplit(":", 1)[-1] if sess.startswith("simulator:event:") else None
