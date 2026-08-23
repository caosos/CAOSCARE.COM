"""Staff-initiated transportation assignment action - lets Front Desk/Admin
manually resolve a request stuck at "Pending - no slot yet" from the
existing daily-ops report and calendar, reusing the exact same booking
engine (transportation_engine.find_or_create_run) that Aria's own /request
path uses, so a staff-assigned ride and a resident-requested one can never
disagree about what counts as "booked".

Split into its own file rather than growing routes/transportation.py
(already 274 lines), matching the existing pattern of
transportation_calendar.py / transportation_resources.py /
transportation_report.py / transportation_voice_context.py, all split out
of transportation.py for the same line-cap reason.

Per docs/reports/ADMIN_PRODUCT_BLUEPRINT.md section 11 and the
2026-08-23 admin visual gap report: a request stuck "Pending" must have a
visible next action. This endpoint IS that action. It never fabricates
driver/vehicle capacity or availability - if none is configured, or none is
free for the requested time, it returns a specific, honest reason the UI
surfaces directly instead of silently failing or hiding the button.
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from deps import db, require_front_desk_or_admin
from routes.receipts import create_receipt
from routes.notifications import notify_department
from transportation_engine import find_or_create_run, to_minutes

router = APIRouter(prefix="/transportation", tags=["transportation-assign"])

OPEN_TASK_STATUSES = ["pending", "in_progress"]


@router.get("/request/{task_id}/assign/context")
async def assign_context(task_id: str, user=Depends(require_front_desk_or_admin)):
    """What staff needs before clicking Assign: the request itself, plus
    whether any drivers/vehicles exist at all, so the UI can explain a
    'nothing to assign' state honestly instead of a generic failure."""
    task = await db.staff_tasks.find_one({"task_id": task_id, "category": "transportation"}, {"_id": 0})
    if not task:
        raise HTTPException(status_code=404, detail="Transportation request not found")
    driver_count = await db.transport_drivers.count_documents({"enabled": True})
    vehicle_count = await db.transport_vehicles.count_documents({"enabled": True})
    return {
        "task_id": task_id, "requested_for_date": task.get("requested_for_date"),
        "requested_for_time_label": task.get("requested_for_time_label"),
        "purpose": task.get("description"), "room": task.get("room"),
        "already_booked": bool(task.get("transport_run_id") or task.get("transport_slot_id")),
        "drivers_configured": driver_count, "vehicles_configured": vehicle_count,
        "resources_configured": driver_count > 0 and vehicle_count > 0,
    }


class AssignInput(BaseModel):
    start_time: str  # "HH:MM" 24h - the exact time staff is committing to


@router.post("/request/{task_id}/assign")
async def assign_transport_request(task_id: str, data: AssignInput, user=Depends(require_front_desk_or_admin)):
    """Staff commits to an exact time for a request that only ever carried a
    free-text label (e.g. "around 10"). Reuses find_or_create_run - the
    identical engine call /request and /request/{id}/change use - so this
    can never produce a different notion of "booked" than Aria's own path."""
    task = await db.staff_tasks.find_one({"task_id": task_id, "category": "transportation"}, {"_id": 0})
    if not task:
        raise HTTPException(status_code=404, detail="Transportation request not found")
    if task["status"] not in OPEN_TASK_STATUSES:
        raise HTTPException(status_code=400, detail=f"Request is already {task['status']}")
    if task.get("transport_run_id") or task.get("transport_slot_id"):
        raise HTTPException(status_code=400, detail="Request is already booked")
    if to_minutes(data.start_time) is None:
        raise HTTPException(status_code=422, detail="start_time must be HH:MM 24h")

    driver_count = await db.transport_drivers.count_documents({"enabled": True})
    vehicle_count = await db.transport_vehicles.count_documents({"enabled": True})
    if driver_count == 0 or vehicle_count == 0:
        missing = [n for n, c in (("drivers", driver_count), ("vehicles", vehicle_count)) if c == 0]
        return {
            "booked": False, "reason": "not_configured",
            "message": (
                f"No {' or '.join(missing)} configured yet - add at least one in "
                "Transport Resources before this request can be assigned."
            ),
        }

    booking = await find_or_create_run(task["requested_for_date"], data.start_time, task.get("description"), task_id)
    run = booking["run"]
    if not run:
        return {
            "booked": False, "reason": "no_availability",
            "message": (
                f"No free driver and vehicle pair for {data.start_time} on "
                f"{task['requested_for_date']} - every configured resource is already "
                "committed to another run in that window."
            ),
        }

    await db.staff_tasks.update_one({"task_id": task_id}, {"$set": {"transport_run_id": run["run_id"]}})
    receipt = await create_receipt(
        action_type="transportation_booked", related_object_type="task", related_object_id=task_id,
        source="staff", resident_id=task.get("resident_id"), room=task.get("room"),
        requested_by=user["user_id"], assigned_role="transportation",
    )
    await notify_department(
        "transportation", "CAOS Care: transportation assigned by staff",
        f"ASSIGNED — {task['requested_for_date']} at {run['depart_time']}\n"
        f"Purpose: {task.get('description')}\nRoom: {task.get('room') or 'unknown'}",
    )
    return {
        "booked": True, "receipt_id": receipt["receipt_id"], "shared": booking["shared"],
        "run": {"date": task["requested_for_date"], "depart_time": run["depart_time"]},
    }
