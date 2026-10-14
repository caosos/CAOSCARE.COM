"""Live Operations dashboard summary (SIM-007A): the running community at a glance.

Read-only.  Counts are exact run-scoped canonical reads; staffing is the
deterministic rota at the moment the database reflects (the last executed
event, so executor lag is never shown as missing staff or longer waits).
"""
from collections import Counter, defaultdict
from datetime import datetime, timezone

from simulation.community_cohort import residents_for
from simulation.community_coverage import OPERATING_HOURS
from simulation.community_dashboard_common import (
    TASK_FIELDS, current_run, default_store, plan_events, scoped, sim_time, ticket_row,
)
from simulation.community_shift_cover import active_covers
from simulation.community_staffing import DEPARTMENT_LABELS, worker_statuses
from simulation.community_runtime_staffing import staffing_at
from simulation.community_timeline import build_90_day_timeline, cohort_of_revision

HORIZON = 90 * 1440


def executed_position(run: dict) -> int:
    """The simulated minute the canonical records currently reflect."""
    clock = run.get("sim_minute") or 0
    try:
        events = build_90_day_timeline(cohort_of_revision(run.get("plan_revision"))).events
    except ValueError:
        return clock
    cursor = run.get("cursor") or 0
    if cursor >= len(events):
        return clock
    upcoming = events[cursor]
    return min(clock, upcoming.day_index * 1440 + upcoming.minute)


def run_header(run: dict, as_of: int) -> dict:
    count = run.get("event_count") or 0
    return {
        "run_id": run.get("run_id"), "state": run.get("state"), "cohort": run.get("cohort"),
        "resident_count": run.get("resident_count"),
        "clock": sim_time(run.get("sim_minute")), "as_of": sim_time(as_of),
        "executor_behind_minutes": max(0, (run.get("sim_minute") or 0) - as_of),
        "progress_percent": round((run.get("cursor") or 0) * 100 / count, 2) if count else None,
        "speed_note": ("The run's configured speed is not recorded on the run yet (SIM-007B); "
                       "the pace shown is measured from the simulated clock."),
    }


def _staff_rows(as_of: int, holding: dict, covers: dict) -> list[dict]:
    rows = []
    for row in worker_statuses(*divmod(min(as_of, HORIZON - 1), 1440)):
        task = holding.get(row["actor_id"])
        cover = covers.get(row["actor_id"])
        rows.append({
            **{key: row[key] for key in ("actor_id", "name", "department", "job_role", "shift")},
            "duty": row["status"],
            "availability": ("covered" if cover else "busy" if task
                             else "free" if row["status"] == "on_duty" else row["status"]),
            "covered_by": (cover or {}).get("covered_by_name"),
            "current_task_id": (task or {}).get("task_id"),
        })
    return rows


async def dashboard_snapshot(*, store=None) -> dict:
    store = store if store is not None else default_store()
    run = await current_run(store)
    if run is None:
        return {"status": "not_started", "read_only": True, "run": None,
                "generated_at": datetime.now(timezone.utc).isoformat()}
    run_id, as_of = run["run_id"], executed_position(run)
    plan = plan_events(run.get("plan_revision") or "")
    base = {**scoped(run_id), "simulated": True}
    counts = {status: await store.staff_tasks.count_documents({**base, "status": status})
              for status in ("pending", "in_progress", "completed")}
    open_tasks = await store.staff_tasks.find(
        {**base, "status": {"$in": ["pending", "in_progress"]}}, TASK_FIELDS).to_list(None)
    today = f"^simulator:event:day-{as_of // 1440:03d}:"
    done_today = Counter()
    for row in await store.staff_tasks.aggregate([
        {"$match": {**base, "status": "completed", "conversation_session_id": {"$regex": today}}},
        {"$group": {"_id": "$category", "n": {"$sum": 1}}},
    ]).to_list(None):
        done_today[row["_id"]] = row["n"]
    rows = [ticket_row(task, plan, as_of) for task in open_tasks]
    holding = {task.get("assigned_to"): task for task in open_tasks if task.get("status") == "in_progress"}
    covers = {row["worker_actor_id"]: row for row in await active_covers(store, run_id)}
    staff = _staff_rows(as_of, holding, covers)
    coverage = staffing_at(min(as_of, HORIZON - 1))["coverage"]

    by_dept = defaultdict(list)
    for row in rows:
        by_dept[row["department"]].append(row)
    departments = []
    for slug, label in DEPARTMENT_LABELS.items():
        mine = by_dept.get(slug, [])
        waits = [row["waiting_minutes"] for row in mine if row["waiting_minutes"] is not None]
        people = [row for row in staff if row["department"] == slug]
        start, end = OPERATING_HOURS[slug]
        departments.append({
            "slug": slug, "label": label, "status": coverage[slug]["status"],
            "hours": "24 hours" if start == end else f"{start}–{end}",
            "on_duty": sum(row["duty"] == "on_duty" for row in people),
            "on_call": sum(row["duty"] == "on_call" for row in people),
            "staff_total": len(people),
            "waiting": sum(row["status"] == "pending" for row in mine),
            "in_progress": sum(row["status"] == "in_progress" for row in mine),
            "completed_today": done_today.get(slug, 0),
            "overdue": sum(row["overdue"] for row in mine),
            "longest_wait_minutes": max(waits) if waits else None,
        })

    open_by_resident = Counter(task.get("resident_id") for task in open_tasks)
    residents = [{"resident_id": r.resident_id, "name": r.name, "room": r.room,
                  "open_requests": open_by_resident.get(r.resident_id, 0)}
                 for r in residents_for(run.get("cohort") or "community_75")]
    return {
        "status": "loaded", "read_only": True,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "run": run_header(run, as_of),
        "counts": {
            "workers_on_duty": sum(row["duty"] == "on_duty" for row in staff),
            "workers_on_call": sum(row["duty"] == "on_call" for row in staff),
            "residents": len(residents),
            "pending": counts["pending"], "in_progress": counts["in_progress"],
            "completed": counts["completed"],
            "overdue": sum(row["overdue"] for row in rows),
        },
        "departments": departments, "staff": staff, "residents": residents,
        "truth": ("Counts are exact reads of this run's canonical tickets. Staffing is the scheduled "
                  "rota at the last executed moment. Overdue = claimable for more than 60 simulated "
                  "minutes (a display threshold, not a care standard)."),
    }
