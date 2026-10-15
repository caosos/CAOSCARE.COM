"""The simulated side of one task, for GET /tasks/{id}/detail (#168).

A living-community ticket has two clocks: the real receipt timestamps every
task carries, and the simulated community clock.  This block tells the
simulated one - when it was requested, started and finished in simulated
time, how long the routine is expected to take, how long it waited and why,
who raised it - from canonical records only: the run row, the run's own
validated plan, and the executor's phase receipts (the same reading the
Live Operations ticket view uses, see :mod:`simulation.community_ticket_view`).
Anything not recorded is ``None``; nothing is inferred.  Read-only.
"""
from typing import Optional

from routes.task_origin import KIND_LABELS, kind_of, routine_name
from simulation.community_blueprint import SIMULATION_SCOPE
from simulation.community_dashboard_common import (
    SESSION_PREFIX, default_store, phases_for, plan_events, sim_time, workflow_of,
)
from simulation.community_dashboard_view import executed_position
from simulation.community_ticket_plan import OPEN, work_minutes
from simulation.community_ticket_view import executed_phase, executor_receipts, timeline


def is_community_ticket(task: dict) -> bool:
    return bool(task.get("simulation_run_id")) and (
        task.get("conversation_session_id") or "").startswith(SESSION_PREFIX)


def _elapsed(task: dict, told: dict, now: Optional[int]) -> dict:
    """Simulated minutes waiting / working so far, or as finally recorded."""
    requested = (told["requested"] or {}).get("absolute_minute")
    started = (told["started"] or {}).get("absolute_minute")
    status = task.get("status")
    waiting = told["wait_minutes"]
    working = told["work_minutes"]
    if status == "pending" and requested is not None and now is not None:
        waiting = max(0, now - requested)
    if status == "in_progress" and started is not None and now is not None:
        working = max(0, now - started)
    return {"waiting_minutes": waiting, "working_minutes": working}


async def task_simulation(task: dict, *, store=None) -> Optional[dict]:
    """The ``simulation`` block for one task, or None for a non-simulated task."""
    if not is_community_ticket(task):
        return None
    store = store if store is not None else default_store()
    run_id = task["simulation_run_id"]
    routine = routine_name(task)
    kind = kind_of(task)
    base = {"run_id": run_id, "workflow": workflow_of(task), "routine": routine,
            "expected_work_minutes": work_minutes(routine) if routine else None,
            "origin": {"kind": kind, "label": KIND_LABELS[kind]}}
    run = await store.sim_runs.find_one({"run_id": run_id, "simulation_scope": SIMULATION_SCOPE},
                                        {"_id": 0})
    if run is None:
        return {**base, "run_found": False, "run_state": None, "now": None, "requested": None,
                "started": None, "finished": None, "basis": None, "wait_reason": None,
                "wait_minutes": None, "recorded_waited_minutes": None, "work_minutes": None,
                "waiting_minutes": None, "working_minutes": None, "raised_by": None}
    phases = phases_for(plan_events(run.get("plan_revision") or ""), base["workflow"])
    receipts = await executor_receipts(store, run_id, base["workflow"])
    told = timeline(task, phases, receipts)
    now = executed_position(run)
    opened = executed_phase(receipts, OPEN)
    raised_by = ({"id": opened.get("actor_id"), "name": opened.get("actor_name"),
                  "type": opened.get("actor_type"), "receipt_id": opened.get("receipt_id")}
                 if opened else None)
    return {**base, "run_found": True, "run_state": run.get("state"), "now": sim_time(now),
            **told, **_elapsed(task, told, now), "raised_by": raised_by}
