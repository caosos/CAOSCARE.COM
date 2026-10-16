"""Shared read helpers for the Live Operations dashboard (SIM-007A).

Read-only.  Everything shown comes from canonical run-scoped records
(StaffTask, receipts, residents, the run row) or from the run's own
validated plan and staffing rota, which are labelled as *planned*.
"""
from functools import lru_cache
from typing import Optional

from simulation.community_blueprint import COMMUNITY_ID, SIMULATION_SCOPE
from simulation.community_ticket_plan import CLAIM, COMPLETE, OPEN, OPEN_TO_CLAIM_MINUTES
from simulation.community_timeline import build_90_day_timeline, cohort_of_revision

SESSION_PREFIX = "simulator:event:"
OVERDUE_AFTER_MINUTES = 60   # display threshold shared with the queue view
TASK_FIELDS = {
    "_id": 0, "task_id": 1, "status": 1, "category": 1, "title": 1, "description": 1,
    "priority": 1, "resident_id": 1, "resident_name": 1, "room": 1, "assigned_to": 1,
    "assigned_name": 1, "conversation_session_id": 1, "created_at": 1, "started_at": 1,
    "completed_at": 1, "completed_by_name": 1, "notes": 1,
}


def default_store():
    from deps import db
    return db


def scoped(run_id: str) -> dict:
    return {"simulation_scope": SIMULATION_SCOPE, "simulation_community_id": COMMUNITY_ID,
            "simulation_run_id": run_id}


def sim_time(absolute_minute: Optional[int]) -> Optional[dict]:
    """Simulated clock label; day is 1-based for people."""
    if absolute_minute is None:
        return None
    day_index, minute = divmod(absolute_minute, 1440)
    return {"absolute_minute": absolute_minute, "day": day_index + 1,
            "hh_mm": f"{minute // 60:02d}:{minute % 60:02d}"}


async def current_run(store) -> Optional[dict]:
    """The RUNNING/PAUSED run, else the most recently updated one."""
    query = {"simulation_scope": SIMULATION_SCOPE, "simulation_community_id": COMMUNITY_ID}
    active = await store.sim_runs.find_one({**query, "state": {"$in": ["RUNNING", "PAUSED"]}},
                                           {"_id": 0})
    if active:
        return active
    return await store.sim_runs.find_one(query, {"_id": 0}, sort=[("updated_at", -1)])


@lru_cache(maxsize=2)
def plan_events(plan_revision: str) -> dict:
    """event_id -> ExecutorEvent for the run's own validated plan."""
    try:
        events = build_90_day_timeline(cohort_of_revision(plan_revision)).events
    except ValueError:
        return {}
    return {event.event_id: event for event in events}


def workflow_of(task: dict) -> str:
    return (task.get("conversation_session_id") or "").removeprefix(SESSION_PREFIX)


def planned_phase(plan: dict, workflow: str, phase: str):
    return plan.get(f"{workflow}:ticket_{phase}")


def describe(task: dict) -> str:
    return task.get("description") or task.get("title") or task.get("notes") or ""


def ticket_row(task: dict, plan: dict, now_minute: Optional[int]) -> dict:
    """One ticket for lists: the canonical record plus its planned request time."""
    workflow = workflow_of(task)
    opened = planned_phase(plan, workflow, OPEN)
    requested = opened.requested_at_minute if opened else None
    waiting = None
    if task.get("status") == "pending" and requested is not None and now_minute is not None:
        waiting = max(0, now_minute - requested)
    holder = task.get("assigned_to") or ""
    return {
        "task_id": task.get("task_id"),
        "what": describe(task),
        "department": task.get("category"),
        "status": task.get("status"),
        "priority": task.get("priority"),
        "resident": {"id": task.get("resident_id"), "name": task.get("resident_name"),
                     "room": task.get("room")},
        "worker": {"id": holder or None, "name": task.get("assigned_name"),
                   "real_staff": bool(holder) and not holder.startswith("sim:staff:")},
        "requested": sim_time(requested),
        "waiting_minutes": waiting,
        "overdue": waiting is not None and waiting - OPEN_TO_CLAIM_MINUTES > OVERDUE_AFTER_MINUTES,
        "routine": opened.action_type if opened else None,
    }


def phases_for(plan: dict, workflow: str) -> dict:
    return {phase: planned_phase(plan, workflow, phase) for phase in (OPEN, CLAIM, COMPLETE)}
