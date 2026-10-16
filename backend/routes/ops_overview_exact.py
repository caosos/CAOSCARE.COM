"""Exact department counts for the Operations overview (#153 slice 2).

The overview's department "open" and "done today" numbers come from the same
query as GET /ops/metrics/records (ops_metrics_query.match_for, live world,
facility wall date), so each number equals the records it opens - with no
row cap. The overview's other department columns are still counted from its
loaded task list; `unverified_reason` says precisely why those cannot be
trusted as complete or live-only when that is the case.
"""
from datetime import datetime
from typing import Optional
from zoneinfo import ZoneInfo

from routes.facility_local_time import facility_tz
from routes.ops_metrics_query import NO_DEPARTMENT, Scope, count_by_department
from routes.task_origin import world_filter

# overview column -> /ops/metrics metric (same filter, same drill-down)
EXACT_COLUMNS = {"open": "open", "completed_today": "done"}
LISTED_COLUMNS = ("overdue", "unassigned", "in_progress")


async def facility_disclosure(store) -> dict:
    """Which facility the counts describe. Tasks carry no facility_id, so a
    count covers every task in this database; say so rather than imply a
    per-facility filter."""
    rows = await store.facilities.find({}, {"_id": 0, "facility_id": 1, "name": 1}).to_list(5)
    if len(rows) == 1:
        return {"facility_id": rows[0].get("facility_id"), "name": rows[0].get("name"),
                "basis": "The only facility in this database; tasks carry no facility_id."}
    if not rows:
        return {"facility_id": None, "name": None,
                "basis": "No facility record is set up; tasks carry no facility_id."}
    return {"facility_id": None, "name": None,
            "basis": f"{len(rows)} facility records; tasks carry no facility_id, so counts cover all of them."}


async def live_scope() -> Scope:
    tz = await facility_tz()
    return Scope("live", tz, date=datetime.now(ZoneInfo(tz)).strftime("%Y-%m-%d"))


async def exact_department_counts(store, loaded: int, cap: int) -> tuple:
    """({column: {department: n}}, disclosure). `loaded` is how many task rows
    the overview's list query returned under `cap`."""
    scope = await live_scope()
    counts = {}
    for column, metric in EXACT_COLUMNS.items():
        counts[column] = {slug: v["total"] for slug, v in (await count_by_department(store, metric, scope)).items()}
    total = await store.staff_tasks.count_documents({})
    simulated = await store.staff_tasks.count_documents(world_filter("simulated"))
    reasons = []
    if loaded >= cap and total > loaded:
        reasons.append(f"counted from the first {loaded:,} of {total:,} task records (unsorted), so not complete")
    if simulated:
        reasons.append(f"includes {simulated:,} simulated task records alongside live ones")
    disclosure = {
        "world": "live", "date": scope.date, "timezone": scope.tz,
        "period_label": scope.period()["label"],
        "facility": await facility_disclosure(store),
        "run": None, "simulated_excluded": simulated, "task_records_total": total,
        "exact_columns": list(EXACT_COLUMNS),
        "explanation": ("Open and done today count live records only (not marked simulated), by department; "
                        f"done today means completed on {scope.date} ({scope.tz}). Simulated runs are in the "
                        "workspace's Simulated view, scoped to one run."),
        "unverified_columns": list(LISTED_COLUMNS) if reasons else [],
        "unverified_reason": ("UNVERIFIED: " + "; ".join(reasons) + ".") if reasons else None,
    }
    return counts, disclosure


def general_count(by_dept: dict) -> int:
    """The General / all-staff row: tasks with no department or the all_staff role."""
    return by_dept.get(NO_DEPARTMENT, 0) + by_dept.get("all_staff", 0)
