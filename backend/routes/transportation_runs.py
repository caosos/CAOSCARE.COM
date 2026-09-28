"""Transportation run lifecycle - the ride actually leaving and finishing.

A TransportRun is confirmed when booked (transportation_engine). This file
owns what happens after that, as staff-confirmed real-world facts: the run
departs (every rider's request goes in progress) and completes (every rider
still on it is completed). Each step writes one receipt per rider so the
request history and Aria's status answer show what actually happened.

Operators are the people who run rides: owner/admin, front desk, and staff
in the transportation department (drivers). Everyone else is rejected.
"""
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel

from deps import db, get_current_user
from models import now_utc
from routes.receipts import create_receipt
from transportation_engine import OPEN_RUN_STATUSES, CLOSED_TASK_STATUSES, reconcile_run
from routes.task_history import update_task_with_history
from routes.transport_task_history import close_events, depart_events

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


async def _rider_receipt(task: dict, action_type: str, user: dict, status: str, result: Optional[str] = None) -> None:
    await create_receipt(
        action_type=action_type, related_object_type="task", related_object_id=task["task_id"],
        source="staff", resident_id=task.get("resident_id"), room=task.get("room"),
        requested_by=user["user_id"], assigned_role="transportation", status=status, result=result,
    )


async def _complete_rider(task: dict, user: dict, now: str, notes: Optional[str]) -> None:
    await update_task_with_history(task["task_id"], {
        "status": "completed", "completed_at": now, "started_at": task.get("started_at") or now,
        "completed_by": user["user_id"], "completed_by_name": user.get("name"),
        **({"notes": notes} if notes else {}),
    }, close_events(task, "completed", user, notes))
    await _rider_receipt(task, "transportation_completed", user, "completed", notes or "Ride completed")


@router.post("/runs/{run_id}/depart")
async def depart_run(run_id: str, user=Depends(require_transport_operator)):
    run = await _open_run(run_id)
    if run["status"] == "in_progress":
        raise HTTPException(status_code=400, detail="Run has already departed")
    riders = await _open_riders(run)
    if not riders:
        raise HTTPException(status_code=400, detail="No riders left on this run")
    now = now_utc().isoformat()
    await db.transport_runs.update_one(
        {"run_id": run_id},
        {"$set": {"status": "in_progress", "departed_at": now, "closed_by_name": user.get("name"), "updated_at": now}},
    )
    for t in riders:
        await update_task_with_history(t["task_id"], {
            "status": "in_progress", "started_at": now,
            "assigned_to": t.get("assigned_to") or user["user_id"],
            "assigned_name": t.get("assigned_name") or user.get("name"),
        }, depart_events(t, user))
        await _rider_receipt(t, "transportation_departed", user, "in_progress", f"Departed at {run['depart_time']}")
    return {"run_id": run_id, "status": "in_progress", "riders": len(riders)}


class CompleteInput(BaseModel):
    notes: Optional[str] = None


@router.post("/runs/{run_id}/complete")
async def complete_run(run_id: str, data: CompleteInput = CompleteInput(), user=Depends(require_transport_operator)):
    run = await _open_run(run_id)
    riders = await _open_riders(run)
    now = now_utc().isoformat()
    for t in riders:
        await _complete_rider(t, user, now, data.notes)
    await db.transport_runs.update_one(
        {"run_id": run_id},
        {"$set": {"status": "completed", "completed_at": now, "closed_by_name": user.get("name"),
                  "updated_at": now, **({"notes": data.notes} if data.notes else {})}},
    )
    return {"run_id": run_id, "status": "completed", "riders": len(riders)}


@router.post("/request/{task_id}/complete")
async def complete_transport_request(task_id: str, data: CompleteInput = CompleteInput(), user=Depends(require_transport_operator)):
    """One rider's ride happened. Staff-confirmed - a real-world fact only
    staff can confirm. Closes the run once no riders are left on it."""
    task = await db.staff_tasks.find_one({"task_id": task_id, "category": "transportation"}, {"_id": 0})
    if not task:
        raise HTTPException(status_code=404, detail="Transportation request not found")
    if task["status"] in CLOSED_TASK_STATUSES:
        raise HTTPException(status_code=400, detail=f"Request is already {task['status']}")
    await _complete_rider(task, user, now_utc().isoformat(), data.notes)
    if task.get("transport_run_id"):
        run = await db.transport_runs.find_one({"run_id": task["transport_run_id"]}, {"_id": 0})
        if run:
            await reconcile_run(run)
    return {"task_id": task_id, "status": "completed"}
