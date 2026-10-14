"""Explainable operations metrics (issue #153).

GET /ops/metrics          per-department Completed / Waiting / In progress
                          counts, each split by origin, for one world
                          (live or simulated) and one reporting period.
GET /ops/metrics/records  the exact tasks behind one of those numbers,
                          searchable and paged; `total` uses the same query
                          as the tile, so the two always agree.

Read-only. Owner/admin see every department; staff see the departments they
act for (staff_scope); anyone else is refused.
"""
import re
from datetime import datetime
from typing import Optional
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query

from deps import db, get_current_user
from routes.facility_local_time import facility_tz
from routes.ops_metrics_query import METRICS, NO_DEPARTMENT, Scope, count_by_department, explain, match_for
from routes.ops_overview_util import dept_label
from routes.staff_scope import ADMIN_ROLES, acting_departments
from routes.task_origin import KIND_LABELS, KINDS, kind_of, routine_name, world_of

router = APIRouter(prefix="/ops/metrics", tags=["ops-metrics"])

ROW_FIELDS = {"_id": 0, "task_id": 1, "title": 1, "description": 1, "status": 1, "visibility_role": 1,
              "source": 1, "template_id": 1, "conversation_session_id": 1, "simulated": 1,
              "simulation_run_id": 1, "resident_id": 1, "resident_name": 1, "room": 1,
              "assigned_to": 1, "assigned_name": 1, "completed_by_name": 1, "created_at": 1,
              "started_at": 1, "completed_at": 1, "priority": 1}


def _viewer_departments(user: dict) -> Optional[set]:
    """None = every department (owner/admin); else the departments the viewer acts for."""
    if user.get("role") in ADMIN_ROLES:
        return None
    depts = acting_departments(user)
    if not depts:
        raise HTTPException(403, "Operations metrics are for staff and administrators")
    return depts


async def _latest_run() -> Optional[dict]:
    active = await db.sim_runs.find_one({"state": {"$in": ["RUNNING", "PAUSED"]}}, {"_id": 0},
                                        sort=[("updated_at", -1)])
    return active or await db.sim_runs.find_one({}, {"_id": 0}, sort=[("updated_at", -1)])


async def _scope(user: dict, world: str, date: Optional[str], run_id: Optional[str],
                 sim_day: Optional[int]) -> tuple:
    if world not in ("live", "simulated"):
        raise HTTPException(422, "world must be live or simulated")
    tz = await facility_tz()
    run = None
    if world == "simulated":
        run = await (db.sim_runs.find_one({"run_id": run_id}, {"_id": 0}) if run_id else _latest_run())
        if not run:
            raise HTTPException(404, "No simulation run found")
        run_id = run["run_id"]
        if sim_day is None:
            sim_day = executed_day(run)
    elif not date:
        date = datetime.now(ZoneInfo(tz)).strftime("%Y-%m-%d")
    elif not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date):
        raise HTTPException(422, "date must be YYYY-MM-DD")
    scope = Scope(world, tz, date=date, run_id=run_id, sim_day=sim_day, departments=_viewer_departments(user))
    return scope, run


def executed_day(run: dict) -> Optional[int]:
    """The simulated day the executor has actually reached (from its last
    executed event); the run clock can be ahead of it."""
    m = re.match(r"day-(\d+):", run.get("last_event_id") or "")
    if m:
        return int(m.group(1))
    return int(run["sim_minute"]) // 1440 if run.get("sim_minute") is not None else None


def _run_summary(run: Optional[dict]) -> Optional[dict]:
    if not run:
        return None
    minute = run.get("sim_minute")
    clock = None
    if minute is not None:
        day, m = divmod(int(minute), 1440)
        clock = {"day": day + 1, "hh_mm": f"{m // 60:02d}:{m % 60:02d}"}
    day = executed_day(run)
    return {"run_id": run.get("run_id"), "state": run.get("state"), "clock": clock,
            "executed_through_day": day + 1 if day is not None else None,
            "scope": run.get("simulation_scope"), "plan_revision": run.get("plan_revision")}


@router.get("")
async def metrics(world: str = "live", date: Optional[str] = None, run_id: Optional[str] = None,
                  sim_day: Optional[int] = Query(None, ge=0), user=Depends(get_current_user)):
    scope, run = await _scope(user, world, date, run_id, sim_day)
    departments = await db.departments.find({}, {"_id": 0}).sort("label", 1).to_list(100)
    by_slug = {d["slug"]: d for d in departments}
    rows: dict = {}
    for metric in METRICS:
        for slug, counts in (await count_by_department(db, metric, scope)).items():
            rows.setdefault(slug, {})[metric] = counts
    for d in departments:
        if d.get("active", True) and (scope.departments is None or d["slug"] in scope.departments):
            rows.setdefault(d["slug"], {})
    empty = {"total": 0, "by_origin": {k: 0 for k in KINDS}}
    out = [{"slug": slug, "label": "No department" if slug == NO_DEPARTMENT else dept_label(slug, by_slug),
            "metrics": {m: rows[slug].get(m, empty) for m in METRICS}} for slug in rows]
    out.sort(key=lambda r: (r["slug"] == NO_DEPARTMENT, r["label"].lower()))
    totals = {m: sum(r["metrics"][m]["total"] for r in out) for m in METRICS}
    return {"world": scope.world, "period": scope.period(), "run": _run_summary(run),
            "metrics": {m: METRICS[m]["label"] for m in METRICS},
            "origins": {k: KIND_LABELS[k] for k in KINDS}, "departments": out, "totals": totals}


def _row(t: dict, by_slug: dict) -> dict:
    kind = kind_of(t)
    return {"task_id": t["task_id"], "summary": t.get("title") or t.get("description") or "",
            "status": t.get("status"), "department": dept_label(t.get("visibility_role"), by_slug),
            "origin": kind, "origin_label": KIND_LABELS[kind], "routine": routine_name(t),
            "world": world_of(t), "source": t.get("source"), "priority": t.get("priority"),
            "resident_id": t.get("resident_id"), "resident_name": t.get("resident_name"), "room": t.get("room"),
            "worker": t.get("completed_by_name") or t.get("assigned_name"), "worker_id": t.get("assigned_to"),
            "created_at": t.get("created_at"), "started_at": t.get("started_at"),
            "completed_at": t.get("completed_at")}


@router.get("/records")
async def metric_records(metric: str, world: str = "live", department: Optional[str] = None,
                         origin: Optional[str] = None, date: Optional[str] = None,
                         run_id: Optional[str] = None, sim_day: Optional[int] = Query(None, ge=0),
                         q: Optional[str] = Query(None, max_length=80), page: int = Query(1, ge=1),
                         page_size: int = Query(50, ge=1, le=200), user=Depends(get_current_user)):
    if metric not in METRICS:
        raise HTTPException(422, f"metric must be one of {', '.join(METRICS)}")
    if origin is not None and origin not in KINDS:
        raise HTTPException(422, f"origin must be one of {', '.join(KINDS)}")
    scope, run = await _scope(user, world, date, run_id, sim_day)
    if department and department != NO_DEPARTMENT and scope.departments is not None \
            and department not in scope.departments:
        raise HTTPException(403, "You can only see your own department's records")
    match = match_for(metric, scope, department, origin)
    total = await db.staff_tasks.count_documents(match)
    if q:
        needle = re.escape(q.strip())
        match = {"$and": [match, {"$or": [{f: {"$regex": needle, "$options": "i"}} for f in
                                          ("title", "description", "resident_name", "room",
                                           "assigned_name", "completed_by_name", "task_id")]}]}
    matched = await db.staff_tasks.count_documents(match) if q else total
    sort_field = "completed_at" if metric == "done" else "created_at"
    docs = await db.staff_tasks.find(match, ROW_FIELDS).sort([(sort_field, -1), ("task_id", 1)]) \
        .skip((page - 1) * page_size).limit(page_size).to_list(page_size)
    departments = await db.departments.find({}, {"_id": 0}).to_list(100)
    by_slug = {d["slug"]: d for d in departments}
    label = None if not department else ("No department" if department == NO_DEPARTMENT
                                          else dept_label(department, by_slug))
    return {"metric": metric, "metric_label": METRICS[metric]["label"], "world": scope.world,
            "period": scope.period(), "run": _run_summary(run), "department": department,
            "origin": origin, "explanation": explain(metric, scope, label, origin),
            "total": total, "matched": matched, "page": page, "page_size": page_size,
            "rows": [_row(t, by_slug) for t in docs]}
