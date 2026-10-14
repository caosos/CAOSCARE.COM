"""One query per dashboard metric (issue #153).

`match_for` builds the Mongo filter for a metric, scope and period; the
tile count (`count_documents`) and the drill-down rows use that same filter,
so a number and the records behind it cannot disagree. `explain` states in
plain words exactly what the filter selects.

Periods:
  live world      - a facility-local calendar date (real wall clock) for
                    completed work; open/in-progress are "right now".
  simulated world - a simulated day of one run: routine events scheduled
                    for that day (the same rule as the Live Operations
                    dashboard); open/in-progress are "right now" in the run.
"""
from datetime import datetime, timedelta
from typing import Optional
from zoneinfo import ZoneInfo

from routes.task_origin import KIND_BASIS, KIND_LABELS, KINDS, kind_filter, world_filter

NO_DEPARTMENT = "no_department"

METRICS = {
    "done": {"label": "Completed", "status": "completed", "dated": True},
    "waiting": {"label": "Waiting", "status": "pending", "dated": False},
    "in_progress": {"label": "In progress", "status": "in_progress", "dated": False},
    "open": {"label": "Open", "status": ["pending", "in_progress"], "dated": False},
    "scheduled": {"label": "Scheduled", "status": None, "dated": True},
}
TILE_METRICS = ("done", "waiting", "in_progress")   # split by origin on /ops/metrics


def _status_filter(status) -> list:
    if status is None:
        return []
    return [{"status": {"$in": status}}] if isinstance(status, list) else [{"status": status}]


def _status_words(status) -> str:
    if status is None:
        return "any status"
    return "status " + (" or ".join(status) if isinstance(status, list) else status)


class Scope:
    """What is being counted: live or simulated world, which run/day/date,
    which departments the viewer may see."""

    def __init__(self, world: str, tz: str, date: Optional[str] = None, run_id: Optional[str] = None,
                 sim_day: Optional[int] = None, departments: Optional[set] = None):
        self.world, self.tz, self.date = world, tz, date
        self.run_id, self.sim_day, self.departments = run_id, sim_day, departments

    def period(self) -> dict:
        if self.world == "simulated":
            return {"kind": "sim_day", "run_id": self.run_id, "sim_day": self.sim_day,
                    "label": f"Simulated day {self.sim_day + 1}" if self.sim_day is not None else "All simulated days"}
        return {"kind": "wall_date", "date": self.date, "timezone": self.tz,
                "label": f"{self.date} ({self.tz})"}


def wall_day_bounds(date: str, tz: str):
    start = datetime.strptime(date, "%Y-%m-%d").replace(tzinfo=ZoneInfo(tz))
    end = start + timedelta(days=1)
    return start.astimezone(ZoneInfo("UTC")), end.astimezone(ZoneInfo("UTC"))


def _on_date(field: str, date: str, tz: str) -> dict:
    """`field` falls on `date` in the facility timezone. Stored as an ISO
    string or a datetime depending on the writer; both are matched."""
    start, end = wall_day_bounds(date, tz)
    return {"$or": [{field: {"$gte": start.isoformat(), "$lt": end.isoformat()}},
                    {field: {"$gte": start, "$lt": end}}]}


def _sim_day(day: int) -> dict:
    return {"conversation_session_id": {"$regex": f"^simulator:event:day-{day:03d}:"}}


def match_for(metric: str, scope: Scope, department: Optional[str] = None,
              origin: Optional[str] = None) -> dict:
    if metric not in METRICS:
        raise ValueError(f"unknown metric {metric}")
    spec = METRICS[metric]
    parts = [world_filter(scope.world), *_status_filter(spec["status"])]
    if scope.world == "simulated" and scope.run_id:
        parts.append({"simulation_run_id": scope.run_id})
    if spec["dated"]:
        if scope.world == "simulated" and scope.sim_day is not None:
            parts.append(_sim_day(scope.sim_day))
        elif scope.world == "live" and scope.date:
            field = "completed_at" if spec["status"] == "completed" else "created_at"
            parts.append(_on_date(field, scope.date, scope.tz))
    if department == NO_DEPARTMENT:
        parts.append({"visibility_role": {"$in": [None, ""]}})
    elif department:
        parts.append({"visibility_role": department})
    elif scope.departments is not None:
        parts.append({"visibility_role": {"$in": sorted(scope.departments)}})
    if origin:
        parts.append(kind_filter(origin))
    return {"$and": parts}


def explain(metric: str, scope: Scope, department_label: Optional[str] = None,
            origin: Optional[str] = None) -> str:
    spec = METRICS[metric]
    where = f"in {department_label}" if department_label else "in every department you can see"
    world = ("simulated records of run " + (scope.run_id or "?")) if scope.world == "simulated" \
        else "live records (not marked simulated)"
    if spec["dated"] and spec["status"] != "completed":
        when = (f"scheduled for simulated day {scope.sim_day + 1}" if scope.world == "simulated"
                and scope.sim_day is not None else
                f"created on {scope.date} ({scope.tz})" if scope.world == "live" and scope.date else "at any time")
    elif spec["dated"]:
        when = (f"scheduled for simulated day {scope.sim_day + 1}" if scope.world == "simulated"
                and scope.sim_day is not None else
                f"completed on {scope.date} ({scope.tz})" if scope.world == "live" and scope.date else "at any time")
    else:
        when = "right now"
    kind = f"; origin: {KIND_LABELS[origin]} ({KIND_BASIS[origin]})" if origin else ""
    return f"Tasks {where} with {_status_words(spec['status'])}, {when}; {world}{kind}."


async def count_by_department(store, metric: str, scope: Scope) -> dict:
    """{department: {"total": n, "by_origin": {kind: n}}} from one aggregation;
    each origin bucket uses the same filter as its drill-down."""
    base = match_for(metric, scope)
    facets = {k: [{"$match": kind_filter(k)}, {"$group": {"_id": "$visibility_role", "n": {"$sum": 1}}}]
              for k in KINDS}
    out: dict = {}
    async for doc in store.staff_tasks.aggregate([{"$match": base}, {"$facet": facets}], allowDiskUse=True):
        for kind, rows in doc.items():
            for row in rows:
                dept = out.setdefault(row["_id"] or NO_DEPARTMENT, {"total": 0, "by_origin": {k: 0 for k in KINDS}})
                dept["by_origin"][kind] = row["n"]
                dept["total"] += row["n"]
    return out
