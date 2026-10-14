"""One ticket, told completely (SIM-007A).

What was asked, by whom, when, which department and worker, when work
started and finished, how long it took, how it ended or why it has not,
and every receipt.  Simulated times come only from executor receipts that
actually executed a phase; real-staff work uses real timestamps.  Each
duration is labelled with its basis so the two are never mixed.
"""
from datetime import datetime

from simulation.community_dashboard_common import (
    current_run, default_store, describe, phases_for, plan_events, scoped, sim_time, ticket_row,
    workflow_of,
)
from simulation.community_dashboard_detail import DashboardNotFound
from simulation.community_dashboard_view import executed_position
from simulation.community_ticket_plan import CLAIM, COMPLETE, OPEN

EXECUTOR = "living_community_executor"
_RECEIPT_FIELDS = {
    "_id": 0, "receipt_id": 1, "action_type": 1, "status": 1, "result": 1, "actor_id": 1,
    "actor_name": 1, "actor_type": 1, "authority": 1, "channel": 1, "created_at": 1,
    "parent_receipt_id": 1, "correlation_id": 1, "simulation_event_id": 1, "before_state": 1,
    "after_state": 1, "next_state": 1, "result_label": 1,
}


def _stamp(value):
    return value.isoformat() if isinstance(value, datetime) else value


def _receipt(row: dict, plan: dict) -> dict:
    event = plan.get(row.get("simulation_event_id") or "")
    return {
        "receipt_id": row.get("receipt_id"), "action": row.get("action_type"),
        "status": row.get("status"), "result": row.get("result"),
        "actor": {"id": row.get("actor_id"), "name": row.get("actor_name"),
                  "type": row.get("actor_type"), "channel": row.get("channel")},
        "authority": row.get("authority"), "parent_receipt_id": row.get("parent_receipt_id"),
        "before": (row.get("before_state") or {}).get("status"),
        "after": (row.get("after_state") or {}).get("status"),
        "next_state": row.get("next_state"),
        "recorded_at": _stamp(row.get("created_at")),
        "simulated_at": sim_time(event.day_index * 1440 + event.minute) if event else None,
        "source": "simulation executor" if row.get("authority") == EXECUTOR else "canonical task service",
    }


def _executed(receipts: list[dict], phase: str):
    return next((r for r in receipts if (r.get("simulation_event_id") or "").endswith(f":ticket_{phase}")
                 and r.get("authority") == EXECUTOR), None)


def _timeline(task: dict, phases: dict, receipts: list[dict]) -> dict:
    claim, finish = _executed(receipts, CLAIM), _executed(receipts, COMPLETE)
    opened = phases[OPEN]
    requested = opened.requested_at_minute if opened else None
    sim_start = (phases[CLAIM].day_index * 1440 + phases[CLAIM].minute
                 if claim and claim.get("status") == "completed" and phases[CLAIM] else None)
    sim_end = (phases[COMPLETE].day_index * 1440 + phases[COMPLETE].minute
               if finish and finish.get("status") == "completed" and phases[COMPLETE] else None)
    out = {"requested": sim_time(requested), "started": sim_time(sim_start),
           "finished": sim_time(sim_end), "basis": "simulated", "wait_minutes": None,
           "work_minutes": None, "wait_reason": (claim or {}).get("after_state", {}).get("wait_reason")}
    if sim_start is not None and requested is not None:
        out["wait_minutes"] = sim_start - requested
    if sim_start is not None and sim_end is not None:
        out["work_minutes"] = sim_end - sim_start
    holder = task.get("assigned_to") or ""
    if holder and not holder.startswith("sim:staff:"):
        # Real staff worked it: report real wall-clock times, labelled as such.
        out.update({"basis": "real time (worked by real staff)",
                    "started_real": _stamp(task.get("started_at")),
                    "finished_real": _stamp(task.get("completed_at"))})
    return out


def _outcome(task: dict, timeline: dict, receipts: list[dict]) -> str:
    status = task.get("status")
    if status == "completed":
        who = task.get("completed_by_name") or task.get("assigned_name") or "staff"
        return f"Completed by {who}." + (f" Note: {task['notes']}" if task.get("notes") else "")
    yielded = next((r for r in reversed(receipts) if r.get("status") == "cancelled"), None)
    if yielded:
        return yielded.get("result") or "The simulated worker yielded this ticket to real staff."
    if status == "in_progress":
        return f"In progress with {task.get('assigned_name') or 'a worker'}."
    return "Waiting in the department queue for an available worker."


async def ticket_detail(task_id: str, *, store=None) -> dict:
    store = store if store is not None else default_store()
    run = await current_run(store)
    if run is None:
        raise DashboardNotFound("no living-community run exists")
    task = await store.staff_tasks.find_one({**scoped(run["run_id"]), "task_id": task_id}, {"_id": 0})
    if task is None:
        raise DashboardNotFound(f"ticket {task_id} is not part of this run")
    plan = plan_events(run.get("plan_revision") or "")
    workflow = workflow_of(task)
    phases = phases_for(plan, workflow)
    event_ids = [f"{workflow}:ticket_{phase}" for phase in (OPEN, CLAIM, COMPLETE)]
    executor = await store.receipts.find(
        {"simulation_run_id": run["run_id"], "simulation_event_id": {"$in": event_ids}},
        _RECEIPT_FIELDS).to_list(None)
    canonical = await store.receipts.find(
        {"related_object_type": "task", "related_object_id": task_id}, _RECEIPT_FIELDS).to_list(None)
    receipts = sorted(executor + canonical, key=lambda r: str(_stamp(r.get("created_at")) or ""))
    timeline = _timeline(task, phases, receipts)
    return {
        "status": "loaded", "run_id": run["run_id"], "as_of": sim_time(executed_position(run)),
        "ticket": {**ticket_row(task, plan, executed_position(run)),
                   "what": describe(task), "title": task.get("title"),
                   "requested_by": {"id": task.get("resident_id"), "name": task.get("resident_name"),
                                    "room": task.get("room")},
                   "source": task.get("source"), "workflow": workflow},
        "timeline": timeline,
        "outcome": _outcome(task, timeline, receipts),
        "receipts": [_receipt(r, plan) for r in receipts],
        "history": [{k: _stamp(v) for k, v in entry.items()} for entry in task.get("event_log") or []],
    }
