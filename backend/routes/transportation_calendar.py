"""Read-only transportation calendar - the same TransportRun/StaffTask data
Aria's booking engine and the Admin daily-ops report use, just shaped for a
day/week timeline view. Split out of transportation.py to stay under the
300-line cap. Readable by Front Desk, transportation staff and Admin/owner (Section 9's
"one source of truth, different role-appropriate views").
"""
from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, Depends

from deps import db
from routes.transportation_runs import require_transport_operator
from transportation_engine import reconcile_run
from routes.realtime_facility import today_facility_date

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
        "requested_for_date": task.get("requested_for_date"), "status": task.get("status"),
        "re_request_count": task.get("re_request_count", 0),
    }


async def _elsewhere(last_shown: str, my_driver: Optional[dict], mine: bool) -> dict:
    """What an empty-looking range hides: the next few later dates with open rides, and how many open,
    unbooked requests are dated before today (they never appear on a future calendar day)."""
    later: dict[str, int] = {}
    run_q = {"date": {"$gt": last_shown}, "status": {"$in": OPEN_RUN_STATUSES}}
    if mine:
        run_q["driver_id"] = my_driver["driver_id"] if my_driver else "__none__"
    for r in await db.transport_runs.find(run_q, {"_id": 0, "date": 1}).to_list(500):
        later[r["date"]] = later.get(r["date"], 0) + 1
    earlier_open = 0
    if not mine:
        base = {"category": "transportation", "status": {"$in": OPEN_TASK_STATUSES}, "transport_run_id": None}
        for t in await db.staff_tasks.find({**base, "requested_for_date": {"$gt": last_shown}}, {"_id": 0, "requested_for_date": 1}).to_list(500):
            later[t["requested_for_date"]] = later.get(t["requested_for_date"], 0) + 1
        earlier_open = await db.staff_tasks.count_documents({**base, "requested_for_date": {"$lt": today_facility_date()}})
    return {"next_dates": [{"date": d, "count": later[d]} for d in sorted(later)[:3]], "earlier_open_unbooked": earlier_open}


@router.get("/calendar")
async def calendar(date: Optional[str] = None, days: int = 1, mine: bool = False, user=Depends(require_transport_operator)):
    """view=day is days=1 (default), view=week is days=7. Every occupied
    window, shared run, and still-pending request for the range comes back
    together so the UI never has to reconstruct the day from separate calls."""
    days = 7 if days >= 7 else 1
    start = date or today_facility_date()   # facility-local, not UTC (UTC is tomorrow after 7 pm Central)
    dates = _date_range(start, days)

    run_q = {"date": {"$in": dates}}
    my_driver = None
    if mine:
        # "My rides": only runs assigned to the driver linked to this login. No linked driver = nothing, never everyone's rides.
        my_driver = await db.transport_drivers.find_one({"user_id": user["user_id"]}, {"_id": 0, "driver_id": 1, "name": 1})
        run_q["driver_id"] = my_driver["driver_id"] if my_driver else "__none__"

    runs = [await reconcile_run(r) for r in await db.transport_runs.find(run_q, {"_id": 0}).to_list(500)]
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
    ).to_list(500) if not mine else []   # unassigned rides are nobody's "mine"

    days_out = []
    for d in dates:
        day_runs = sorted((r for r in runs if r["date"] == d), key=lambda r: r["depart_time"])
        days_out.append({
            "date": d,
            "runs": [
                {
                    "run_id": r["run_id"], "depart_time": r["depart_time"], "return_time": r.get("return_time"),
                    "status": r["status"], "destination": r.get("destination"),
                    "departed_at": r.get("departed_at"), "completed_at": r.get("completed_at"),
                    "closed_by_name": r.get("closed_by_name"),
                    "driver": drivers.get(r.get("driver_id")),
                    "vehicle": vehicles.get(r.get("vehicle_id")),
                    # a ride that was moved to another run is not a rider here any more (the old run keeps the id until released)
                    "riders": [_rider_view(tasks_by_id[tid]) for tid in r.get("resident_task_ids", [])
                               if tid in tasks_by_id and tasks_by_id[tid].get("transport_run_id") in (None, r["run_id"])],
                }
                for r in day_runs if r["status"] in OPEN_RUN_STATUSES or r["status"] in ("completed", "cancelled")
            ],
            "pending": [_rider_view(t) | {"received_at": t.get("created_at")} for t in pending_tasks if t.get("requested_for_date") == d],
        })

    out = {"start_date": start, "days": days_out, "elsewhere": await _elsewhere(dates[-1], my_driver if mine else None, mine)}
    if mine:
        out["mine"] = True
        out["linked_driver"] = my_driver["name"] if my_driver else None
    return out
