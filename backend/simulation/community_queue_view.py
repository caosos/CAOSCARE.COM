"""Read-only Live Operations queue: who is waiting, who is working, who is free.

Ticket state comes from exact run-scoped canonical StaffTask reads.  A
ticket's original request minute comes from the run's own validated plan
(the same deterministic timeline the executor runs), so its wait is
simulated minutes, never wall-clock time.  Failed reads stay unknown.

When the executor is behind the clock, the database reflects the moment of
the next unexecuted event, not the clock.  Waits and staffing are therefore
measured as of that moment and the gap is reported, so executor lag is never
shown as residents waiting longer or as staff missing.
"""
from collections import defaultdict
from functools import lru_cache

from simulation.community_blueprint import COMMUNITY_ID, SIMULATION_SCOPE
from simulation.community_runtime_staffing import staffing_at
from simulation.community_staffing import DEPARTMENT_LABELS
from simulation.community_ticket_plan import OPEN, OPEN_TO_CLAIM_MINUTES
from simulation.community_capacity_schedule import HORIZON_MINUTES
from simulation.community_timeline import build_90_day_timeline, cohort_of_revision

QUEUED_LIMIT = 40
# Display threshold, not a care standard: a ticket claimable for longer
# than this is shown as overdue.
OVERDUE_AFTER_MINUTES = 60
SESSION_PREFIX = "simulator:event:"


def _default_store():
    from deps import db
    return db


@lru_cache(maxsize=4)
def _requested_minutes(plan_revision: str) -> dict[str, int]:
    events = build_90_day_timeline(cohort_of_revision(plan_revision)).events
    return {row.workflow_event_id: row.requested_at_minute
            for row in events if row.task_phase == OPEN and row.requested_at_minute is not None}


def _unknown(status: str, run_id) -> dict:
    return {"schema_version": 1, "status": status, "read_only": True, "run_id": run_id,
            "overdue_after_minutes": OVERDUE_AFTER_MINUTES, "departments": None,
            "queued": None, "workers": None, "anomalies": None}


def _worker(row: dict, active: dict | None) -> dict:
    return {
        "actor_id": row["actor_id"], "name": row["name"], "department": row["department"],
        "job_role": row["job_role"], "shift": row["shift"],
        "availability": "busy" if active else "free",
        "task_id": (active or {}).get("task_id"),
    }


async def queue_snapshot(*, run_id, clock_minute, next_event_minute=None, store=None) -> dict:
    """Queued tickets with their simulated wait, worker availability and backlog."""
    if not run_id or clock_minute is None:
        return _unknown("not_started" if not run_id else "unknown", run_id)
    as_of = clock_minute if next_event_minute is None else min(clock_minute, next_event_minute)
    staffing = staffing_at(as_of) if as_of < HORIZON_MINUTES else {"workers": [], "coverage": {}}
    absolute_minute = as_of
    store = store if store is not None else _default_store()
    scoped = {"simulation_scope": SIMULATION_SCOPE, "simulation_community_id": COMMUNITY_ID,
              "simulation_run_id": run_id, "simulated": True}
    projection = {"_id": 0, "task_id": 1, "category": 1, "priority": 1, "summary": 1,
                  "resident_id": 1, "conversation_session_id": 1, "assigned_to": 1}
    try:
        run = await store.sim_runs.find_one({"run_id": run_id}, {"_id": 0, "plan_revision": 1})
        requested = _requested_minutes((run or {}).get("plan_revision") or "")
        pending = await store.staff_tasks.find({**scoped, "status": "pending"}, projection).to_list(None)
        working = await store.staff_tasks.find({**scoped, "status": "in_progress"}, projection).to_list(None)
    except Exception as exc:  # noqa: BLE001 - surfaced as an unknown read, never as zero
        return {**_unknown("error", run_id), "error": type(exc).__name__}

    queued = []
    for task in pending:
        workflow = (task.get("conversation_session_id") or "").removeprefix(SESSION_PREFIX)
        minute = requested.get(workflow)
        waiting = None if minute is None else max(0, absolute_minute - minute)
        claimable = None if minute is None else max(0, absolute_minute - minute - OPEN_TO_CLAIM_MINUTES)
        queued.append({
            "task_id": task.get("task_id"), "department": task.get("category"),
            "priority": task.get("priority"), "summary": task.get("summary"),
            "resident_id": task.get("resident_id"), "requested_at_minute": minute,
            "waiting_minutes": waiting,
            "overdue": claimable is not None and claimable > OVERDUE_AFTER_MINUTES,
        })
    queued.sort(key=lambda row: (row["waiting_minutes"] is None, -(row["waiting_minutes"] or 0),
                                 row["task_id"] or ""))

    held = defaultdict(list)
    for task in working:
        held[task.get("assigned_to")].append(task)
    on_site = {row["actor_id"] for row in staffing["workers"]}
    workers = [_worker(row, (held.get(row["actor_id"]) or [None])[0]) for row in staffing["workers"]]
    anomalies = (
        [{"kind": "worker_holds_multiple_active_tickets", "actor_id": actor,
          "task_ids": sorted(t.get("task_id") for t in tasks)}
         for actor, tasks in sorted(held.items(), key=lambda item: str(item[0])) if len(tasks) > 1]
        + [{"kind": "active_ticket_held_by_off_site_worker", "actor_id": actor,
            "task_ids": sorted(t.get("task_id") for t in tasks)}
           for actor, tasks in sorted(held.items(), key=lambda item: str(item[0])) if actor not in on_site]
    )

    departments = {}
    coverage = staffing.get("coverage") or {}
    for key, label in DEPARTMENT_LABELS.items():
        rows = [row for row in queued if row["department"] == key]
        staff = [row for row in workers if row["department"] == key]
        waits = [row["waiting_minutes"] for row in rows if row["waiting_minutes"] is not None]
        departments[key] = {
            "label": label, "status": (coverage.get(key) or {}).get("status"),
            "queued": len(rows), "overdue": sum(row["overdue"] for row in rows),
            "longest_wait_minutes": max(waits) if waits else None,
            "in_progress": sum(task.get("category") == key for task in working),
            "on_site": len(staff), "busy": sum(row["availability"] == "busy" for row in staff),
            "free": sum(row["availability"] == "free" for row in staff),
            "on_call": (coverage.get(key) or {}).get("on_call"),
        }
    return {
        "schema_version": 1, "status": "loaded", "read_only": True, "run_id": run_id,
        "basis": "canonical run-scoped tickets; request minute from the run's validated plan",
        "clock_minute": clock_minute, "as_of_minute": as_of,
        "executor_behind_clock_minutes": clock_minute - as_of,
        "overdue_after_minutes": OVERDUE_AFTER_MINUTES,
        "totals": {"queued": len(queued), "overdue": sum(row["overdue"] for row in queued),
                   "in_progress": len(working),
                   "longest_wait_minutes": max((row["waiting_minutes"] or 0 for row in queued), default=None)},
        "departments": departments, "queued": queued[:QUEUED_LIMIT],
        "queued_shown": min(len(queued), QUEUED_LIMIT), "workers": workers,
        "anomalies": anomalies,
    }
