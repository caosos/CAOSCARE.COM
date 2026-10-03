"""Transportation run lifecycle - the ride actually leaving and finishing.

A TransportRun is confirmed when booked (transportation_engine). This file
owns what happens after that, as staff-confirmed real-world facts: the run
departs (every rider's request goes in progress) and completes (every rider
still on it is completed). Each rider's step is a task_lifecycle transition
with its own receipt chained to that ride's origin (SC-15), so the request
history and Aria's status answer show what actually happened. A rider whose
step is refused (no recorded origin) is left unchanged and reported.

Operators are the people who run rides: owner/admin, front desk, and staff
in the transportation department (drivers). Everyone else is rejected.
"""
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel

from deps import db, get_current_user
from models import now_utc
from transportation_engine import OPEN_RUN_STATUSES, CLOSED_TASK_STATUSES, reconcile_run
from routes import task_lifecycle
from routes.transport_task_history import close_events, depart_events, ride_actor, ride_authority

router = APIRouter(prefix="/transportation", tags=["transportation-runs"])


async def require_transport_operator(request: Request) -> dict:
    user = await get_current_user(request)
    if user.get("role") in ("owner", "admin", "front_desk"):
        return user
    if user.get("role") == "staff" and user.get("department") == "transportation":
        return user
    raise HTTPException(status_code=403, detail="Transportation, front desk or admin access required")


async def _open_run(run_id: str) -> dict:
    run = await db.transport_runs.find_one({"run_id": run_id}, {"_id": 0})
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    run = await reconcile_run(run)
    if run["status"] not in OPEN_RUN_STATUSES:
        raise HTTPException(status_code=400, detail=f"Run is already {run['status']}")
    return run


async def _open_riders(run: dict) -> list[dict]:
    return await db.staff_tasks.find(
        {"task_id": {"$in": run.get("resident_task_ids", [])}, "status": {"$nin": CLOSED_TASK_STATUSES}},
        {"_id": 0},
    ).to_list(50)


async def _allowed_riders(riders: list[dict], user: dict, action: str) -> tuple[list, list]:
    """Check every rider before the run changes; a refused rider (recorded by
    the lifecycle) stays as it is and is reported back."""
    ok, refused = [], []
    for t in riders:
        try:
            await task_lifecycle.check(t["task_id"], ride_actor(user, t, "staff"), user,
                                       action=action, authority=ride_authority(user))
            ok.append(t)
        except task_lifecycle.LifecycleError:
            refused.append(t["task_id"])
    return ok, refused


async def _complete_rider(task: dict, user: dict, now: str, notes: Optional[str]) -> None:
    actor = ride_actor(user, task, "staff")
    await task_lifecycle.transition(
        task["task_id"], actor, user, action="complete", authority=ride_authority(user),
        action_type="transportation_completed", status="completed", result=notes or "Ride completed",
        build=lambda t, rid: ({
            "status": "completed", "completed_at": now, "started_at": t.get("started_at") or now,
            "completed_by": user["user_id"], "completed_by_name": user.get("name"),
            **({"notes": notes} if notes else {}),
        }, close_events(t, "completed", actor, rid, notes)))


@router.post("/runs/{run_id}/depart")
async def depart_run(run_id: str, user=Depends(require_transport_operator)):
    run = await _open_run(run_id)
    if run["status"] == "in_progress":
        raise HTTPException(status_code=400, detail="Run has already departed")
    riders, refused = await _allowed_riders(await _open_riders(run), user, "depart")
    if not riders:
        raise HTTPException(status_code=400, detail="No riders left on this run")
    now = now_utc().isoformat()
    await db.transport_runs.update_one(
        {"run_id": run_id},
        {"$set": {"status": "in_progress", "departed_at": now, "closed_by_name": user.get("name"), "updated_at": now}},
    )
    for t in riders:
        actor = ride_actor(user, t, "staff")
        await task_lifecycle.transition(
            t["task_id"], actor, user, action="depart", authority=ride_authority(user),
            action_type="transportation_departed", status="in_progress",
            result=f"Departed at {run['depart_time']}",
            build=lambda t, rid, actor=actor: ({
                "status": "in_progress", "started_at": now,
                "assigned_to": t.get("assigned_to") or user["user_id"],
                "assigned_name": t.get("assigned_name") or user.get("name"),
            }, depart_events(t, actor, rid)))
    return {"run_id": run_id, "status": "in_progress", "riders": len(riders), "refused": refused}


class CompleteInput(BaseModel):
    notes: Optional[str] = None


@router.post("/runs/{run_id}/complete")
async def complete_run(run_id: str, data: CompleteInput = CompleteInput(), user=Depends(require_transport_operator)):
    run = await _open_run(run_id)
    riders, refused = await _allowed_riders(await _open_riders(run), user, "complete")
    now = now_utc().isoformat()
    for t in riders:
        await _complete_rider(t, user, now, data.notes)
    await db.transport_runs.update_one(
        {"run_id": run_id},
        {"$set": {"status": "completed", "completed_at": now, "closed_by_name": user.get("name"),
                  "updated_at": now, **({"notes": data.notes} if data.notes else {})}},
    )
    return {"run_id": run_id, "status": "completed", "riders": len(riders), "refused": refused}


@router.post("/request/{task_id}/complete")
async def complete_transport_request(task_id: str, data: CompleteInput = CompleteInput(), user=Depends(require_transport_operator)):
    """One rider's ride happened. Staff-confirmed - a real-world fact only
    staff can confirm. Closes the run once no riders are left on it."""
    task = await db.staff_tasks.find_one({"task_id": task_id, "category": "transportation"}, {"_id": 0})
    if not task:
        raise HTTPException(status_code=404, detail="Transportation request not found")
    if task["status"] in CLOSED_TASK_STATUSES:
        await task_lifecycle.record_refusal(
            task, ride_actor(user, task, "staff"), ride_authority(user), "complete",
            f"request is already {task['status']}: closed requests are not changed; nothing changed")
        raise HTTPException(status_code=400, detail=f"Request is already {task['status']}")
    await _complete_rider(task, user, now_utc().isoformat(), data.notes)
    if task.get("transport_run_id"):
        run = await db.transport_runs.find_one({"run_id": task["transport_run_id"]}, {"_id": 0})
        if run:
            await reconcile_run(run)
    return {"task_id": task_id, "status": "completed"}
