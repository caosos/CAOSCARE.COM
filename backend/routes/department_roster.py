"""Who works in a department right now — real staff and simulated workers.

GET /departments/{slug}/roster   owner/admin, or anyone who acts for the department

CO-008: the department pages listed only login accounts (db.users), so in a
community run by the simulator they said "no one works here" while the
simulator showed its workers. The simulated workers are deliberately not
user accounts; they live in the staffing rota. This read returns both, each
labelled, from the same sources the simulator dashboard uses
(simulation.community_dashboard_detail.department_detail), so the two screens
describe the same community:

  REAL  authenticated users of the department (no shift data is recorded for
        them yet, so duty is "not recorded", never guessed)
  SIM   the run's rota at the last executed simulated moment: shift, on duty /
        off duty / on call, busy / available, current task, who covers the
        shift, tasks completed on that simulated day
Read-only.
"""
import asyncio
from fastapi import APIRouter, Depends, HTTPException

from deps import db, get_current_user
from routes.staff_scope import acts_for, members_query

router = APIRouter(prefix="/departments", tags=["departments"])


async def _real(slug: str) -> list:
    users = await db.users.find(members_query(slug), {"_id": 0, "user_id": 1, "name": 1, "role": 1}) \
        .sort("name", 1).to_list(200)
    busy = {t["assigned_to"]: t for t in await db.staff_tasks.find(
        {"assigned_to": {"$in": [u["user_id"] for u in users]}, "status": "in_progress"},
        {"_id": 0, "task_id": 1, "title": 1, "assigned_to": 1}).to_list(400)}
    return [{"id": u["user_id"], "name": u.get("name"), "job_role": u.get("role"), "kind": "real",
             "duty": "not_recorded", "shift": None, "availability": "busy" if u["user_id"] in busy else "available",
             "current": busy.get(u["user_id"]), "covered_by": None, "completed_today": None} for u in users]


async def _simulated(slug: str):
    from simulation.community_dashboard_common import current_run
    from simulation.community_dashboard_detail import DashboardNotFound, department_detail
    from simulation.community_dashboard_view import executed_position
    run = await current_run(db)
    if run is None:
        return None
    await asyncio.to_thread(executed_position, run)   # build/cache the run's plan off the event loop
    try:
        detail = await department_detail(slug, store=db)
    except DashboardNotFound:
        return None
    day = detail["day"] - 1
    done = {}
    async for g in db.staff_tasks.aggregate([
        {"$match": {"simulation_run_id": run["run_id"], "visibility_role": slug, "status": "completed",
                    "conversation_session_id": {"$regex": f"^simulator:event:day-{day:03d}:"}}},
        {"$group": {"_id": "$assigned_to", "n": {"$sum": 1}}}]):
        done[g["_id"]] = g["n"]
    people = [{"id": p["actor_id"], "name": p["name"], "job_role": p["job_role"], "kind": "sim",
               "duty": p["duty"], "shift": p["shift"],
               "availability": "covered" if p.get("covered_by") else "busy" if p.get("current") else
               ("available" if p["duty"] == "on_duty" else p["duty"]),
               "current": ({"task_id": p["current"]["task_id"], "title": p["current"].get("what")}
                           if p.get("current") else None),
               "covered_by": p.get("covered_by"), "completed_today": done.get(p["actor_id"], 0),
               "today": p.get("today")} for p in detail["people"]]
    return {"run_id": run["run_id"], "run_state": run.get("state"), "as_of": detail["as_of"],
            "day": detail["day"], "people": people, "schedule_today": detail["schedule_today"]}


@router.get("/{slug}/roster")
async def department_roster(slug: str, user=Depends(get_current_user)):
    if not acts_for(user, slug):
        raise HTTPException(403, "Not allowed to see this department's roster")
    if not await db.departments.find_one({"slug": slug}, {"_id": 1}):
        raise HTTPException(404, "Department not found")
    real = await _real(slug)
    sim = await _simulated(slug)
    people = real + (sim["people"] if sim else [])
    return {"department": slug, "real_count": len(real), "sim_count": len(sim["people"]) if sim else 0,
            "on_duty": sum(1 for p in people if p["duty"] == "on_duty"),
            "simulation": {k: sim[k] for k in ("run_id", "run_state", "as_of", "day", "schedule_today")} if sim else None,
            "people": people,
            "note": ("Simulated workers (SIM) are not user accounts: the simulator gives them their work from "
                     "its plan, so they are not offered in Assign to. A real person can cover a SIM worker's "
                     "shift from Live operations.") if sim else None}
