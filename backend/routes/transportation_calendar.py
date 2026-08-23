"""Read-only transportation calendar - the same TransportRun/StaffTask data
Aria's booking engine and the Admin daily-ops report use, just shaped for a
day/week timeline view. Split out of transportation.py to stay under the
300-line cap. Readable by Front Desk as well as Admin/owner (Section 9's
"one source of truth, different role-appropriate views").
"""
from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, Depends

from deps import db, require_front_desk_or_admin

router = APIRouter(prefix="/transportation", tags=["transportation-calendar"])

OPEN_TASK_STATUSES = ["pending", "in_progress"]
OPEN_RUN_STATUSES = ["confirmed", "in_progress"]


def _date_range(start: str, days: int) -> list[str]:
    d0 = datetime.fromisoformat(start)
    return [(d0 + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(days)]


async def _resource_lookup(ids: set[str], collection) -> dict:
    if not ids:
        return {}
    field = "driver_id" if collection.name == "transport_drivers" else "vehicle_id"
    docs = await collection.find({field: {"$in": list(ids)}}, {"_id": 0}).to_list(len(ids))
    return {d[field]: d for d in docs}


def _rider_view(task: dict) -> dict:
    return {
        "task_id": task["task_id"], "resident_id": task.get("resident_id"),
        "resident_name": task.get("resident_name"), "room": task.get("room"),
        "purpose": task.get("description"), "requested_for_time_label": task.get("requested_for_time_label"),
    }


@router.get("/calendar")
async def calendar(date: Optional[str] = None, days: int = 1, user=Depends(require_front_desk_or_admin)):
    """view=day is days=1 (default), view=week is days=7. Every occupied
    window, shared run, and still-pending request for the range comes back
    together so the UI never has to reconstruct the day from separate calls."""
    days = 7 if days >= 7 else 1
    start = date or datetime.utcnow().strftime("%Y-%m-%d")
    dates = _date_range(start, days)

    runs = await db.transport_runs.find({"date": {"$in": dates}}, {"_id": 0}).to_list(500)
    driver_ids = {r["driver_id"] for r in runs if r.get("driver_id")}
    vehicle_ids = {r["vehicle_id"] for r in runs if r.get("vehicle_id")}
    drivers = await _resource_lookup(driver_ids, db.transport_drivers)
    vehicles = await _resource_lookup(vehicle_ids, db.transport_vehicles)

    all_task_ids = {tid for r in runs for tid in r.get("resident_task_ids", [])}
    tasks_by_id = {}
    if all_task_ids:
        for t in await db.staff_tasks.find({"task_id": {"$in": list(all_task_ids)}}, {"_id": 0}).to_list(500):
            tasks_by_id[t["task_id"]] = t

    pending_tasks = await db.staff_tasks.find(
        {"category": "transportation", "status": {"$in": OPEN_TASK_STATUSES}, "transport_run_id": None,
         "requested_for_date": {"$in": dates}},
        {"_id": 0},
    ).to_list(500)

    days_out = []
    for d in dates:
        day_runs = [r for r in runs if r["date"] == d]
        days_out.append({
            "date": d,
            "runs": [
                {
                    "run_id": r["run_id"], "depart_time": r["depart_time"], "return_time": r.get("return_time"),
                    "status": r["status"], "destination": r.get("destination"),
                    "driver": drivers.get(r.get("driver_id")),
                    "vehicle": vehicles.get(r.get("vehicle_id")),
                    "riders": [_rider_view(tasks_by_id[tid]) for tid in r.get("resident_task_ids", []) if tid in tasks_by_id],
                }
                for r in day_runs if r["status"] in OPEN_RUN_STATUSES or r["status"] in ("completed", "cancelled")
            ],
            "pending": [_rider_view(t) | {"received_at": t.get("created_at")} for t in pending_tasks if t.get("requested_for_date") == d],
        })

    return {"start_date": start, "days": days_out}
