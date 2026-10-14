"""Workspace boxes that are not task counts: residents, staff on duty and
today's activity events. Each answer carries its value, the exact rows it
counts, and a plain explanation; when CAOSCare has no record that could
answer truthfully, the value is null with the reason (never a made-up zero).

GET /ops/metrics/widgets/{name}?world=live|simulated[&date][&run_id][&sim_day]
"""
import asyncio
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from deps import db, get_current_user
from routes.ops_metrics import _scope, _run_summary, _viewer_departments
from routes.ops_metrics_query import explain, match_for

router = APIRouter(prefix="/ops/metrics/widgets", tags=["ops-metrics"])
LIVE_RESIDENT = {"synthetic": {"$ne": True}, "simulation_community_id": {"$exists": False},
                 "simulation_scope": {"$exists": False}}


async def _residents(scope, run) -> dict:
    if scope.world == "simulated":
        q = {"simulation_community_id": {"$exists": True}}
        what = "Synthetic residents provisioned for the simulated community"
    else:
        q = LIVE_RESIDENT
        what = "Resident records not marked synthetic or simulated"
    rows = await db.residents.find(q, {"_id": 0, "resident_id": 1, "name": 1, "preferred_name": 1, "room": 1}) \
        .sort("room", 1).to_list(1000)
    return {"value": len(rows), "explanation": f"{what}.",
            "rows": [{"id": r["resident_id"], "name": r.get("preferred_name") or r.get("name"),
                      "detail": f"Room {r.get('room') or '—'}"} for r in rows]}


async def _staff_on_duty(scope, run) -> dict:
    if scope.world == "live":
        return {"value": None, "rows": [],
                "explanation": "Staff on duty right now.",
                "unverified": "CAOSCare does not record staff clock-in or shift attendance yet, "
                              "so there is no record that could show who is on duty."}
    from simulation.community_dashboard_view import executed_position
    from simulation.community_staffing import worker_statuses
    # Building the run's plan is CPU-heavy the first time (cached after), so
    # it runs off the event loop instead of stalling every other request.
    as_of = await asyncio.to_thread(executed_position, run)
    rows = [w for w in worker_statuses(*divmod(min(as_of, 90 * 1440 - 1), 1440)) if w["status"] == "on_duty"]
    day, minute = divmod(as_of, 1440)
    return {"value": len(rows),
            "explanation": (f"Simulated workers on site per the staffing rota at the last executed moment "
                            f"(day {day + 1}, {minute // 60:02d}:{minute % 60:02d}). On-call staff are not counted."),
            "rows": [{"id": w["actor_id"], "name": w["name"],
                      "detail": f"{w['department']} · {w['job_role']} · {w['shift']}"} for w in rows]}


async def _events_today(scope, run) -> dict:
    if scope.world == "simulated":
        match = match_for("scheduled", scope, "activities")
        rows = await db.staff_tasks.find(match, {"_id": 0, "task_id": 1, "title": 1, "resident_name": 1,
                                                 "status": 1}).sort("task_id", 1).to_list(500)
        return {"value": await db.staff_tasks.count_documents(match),
                "explanation": explain("scheduled", scope, "Activities"),
                "rows": [{"id": t["task_id"], "name": t.get("title"),
                          "detail": f"{t.get('resident_name') or ''} · {t.get('status')}", "task_id": t["task_id"]}
                         for t in rows]}
    from routes.schedule import public_today
    items = await public_today(date=scope.date, category=None)
    return {"value": len(items),
            "explanation": f"Published activity schedule items for {scope.date} (resident-facing, staff-only "
                           "categories excluded) — the same list Aria reads to residents.",
            "rows": [{"id": f"{i.get('time_label')}-{n}", "name": i["title"],
                      "detail": f"{i.get('time_label') or ''} · {i.get('category')}"} for n, i in enumerate(items)]}


WIDGETS = {"residents": _residents, "staff_on_duty": _staff_on_duty, "events_today": _events_today}


@router.get("/{name}")
async def widget(name: str, world: str = "live", date: Optional[str] = None, run_id: Optional[str] = None,
                 sim_day: Optional[int] = Query(None, ge=0), user=Depends(get_current_user)):
    if name not in WIDGETS:
        raise HTTPException(404, "Unknown widget")
    if _viewer_departments(user) is not None:
        raise HTTPException(403, "This box is for administrators")
    scope, run = await _scope(user, world, date, run_id, sim_day)
    out = await WIDGETS[name](scope, run)
    return {"name": name, "world": scope.world, "period": scope.period(), "run": _run_summary(run),
            "total": len(out["rows"]), **out}
