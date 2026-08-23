"""Resource-aware transportation booking engine (driver + vehicle + run).

Pure domain logic, no FastAPI router - imported by routes/transportation.py
(resident-request booking), routes/transportation_resources.py (driver/
vehicle CRUD), and routes/transportation_calendar.py (read-only calendar).
This is the single place that decides whether a request can be confirmed,
so Aria/Admin/Front Desk can never see different answers.

Compatibility is deterministic and defaults to "uncertain -> pending":
sharing an existing run requires an exact destination match AND the new
time falling inside the existing run's occupied window; a new run requires
an actually-free (driver, vehicle) pair. No fixed trip-duration or vehicle
capacity is assumed - only what's explicitly known or configured.
"""
from typing import Optional
from deps import db
from models import now_utc
from models_transportation import TransportRun, TransportSchedulingConfig

DEFAULT_BUFFER_MINUTES = 30  # policy default shown as an editable setting, not a claim about any trip
OPEN_RUN_STATUSES = ["confirmed", "in_progress"]


def to_minutes(hhmm: str) -> Optional[int]:
    try:
        h, m = hhmm.split(":")
        return int(h) * 60 + int(m)
    except Exception:
        return None


def _run_window(run: dict, buffer_minutes: int) -> tuple[int, int]:
    """Occupied window in minutes-since-midnight. Only extends past the
    departure when a return time is actually known - never guessed."""
    start = to_minutes(run["depart_time"]) or 0
    end = to_minutes(run["return_time"]) if run.get("return_time") else start
    return (start - buffer_minutes, (end or start) + buffer_minutes)


def _overlaps(a: tuple[int, int], b: tuple[int, int]) -> bool:
    return a[0] < b[1] and b[0] < a[1]


async def get_scheduling_config() -> dict:
    doc = await db.transport_scheduling_config.find_one({"config_id": "transport_scheduling"}, {"_id": 0})
    if doc:
        return doc
    default = TransportSchedulingConfig(buffer_minutes=DEFAULT_BUFFER_MINUTES).model_dump()
    default["updated_at"] = default["updated_at"].isoformat()
    await db.transport_scheduling_config.insert_one({**default})
    return default


async def _runs_for_date(date: str) -> list[dict]:
    return await db.transport_runs.find({"date": date, "status": {"$in": OPEN_RUN_STATUSES}}, {"_id": 0}).to_list(200)


async def _find_shareable_run(date: str, window: tuple[int, int], destination: Optional[str], buffer_minutes: int) -> Optional[dict]:
    if not destination:
        return None  # can't confirm travel compatibility without a known destination - never guess
    dest_norm = destination.strip().lower()
    for run in await _runs_for_date(date):
        if (run.get("destination") or "").strip().lower() != dest_norm:
            continue
        if not _overlaps(window, _run_window(run, buffer_minutes)):
            continue
        vehicle = await db.transport_vehicles.find_one({"vehicle_id": run.get("vehicle_id")}, {"_id": 0}) if run.get("vehicle_id") else None
        capacity = vehicle.get("capacity") if vehicle else None
        if capacity is None:
            continue  # unconfigured capacity - never assume there's room
        if len(run.get("resident_task_ids", [])) >= capacity:
            continue
        return run
    return None


async def find_free_resource_pair(date: str, window: tuple[int, int], buffer_minutes: int) -> tuple[Optional[dict], Optional[dict]]:
    runs = await _runs_for_date(date)
    busy_driver_ids = {r["driver_id"] for r in runs if r.get("driver_id") and _overlaps(window, _run_window(r, buffer_minutes))}
    busy_vehicle_ids = {r["vehicle_id"] for r in runs if r.get("vehicle_id") and _overlaps(window, _run_window(r, buffer_minutes))}

    drivers = await db.transport_drivers.find({"enabled": True}, {"_id": 0}).sort("is_flex", 1).to_list(50)
    vehicles = await db.transport_vehicles.find({"enabled": True}, {"_id": 0}).to_list(50)
    free_driver = next((d for d in drivers if d["driver_id"] not in busy_driver_ids), None)
    free_vehicle = next((v for v in vehicles if v["vehicle_id"] not in busy_vehicle_ids), None)
    return free_driver, free_vehicle


async def find_or_create_run(
    date: str, start_time: Optional[str], destination: Optional[str],
    resident_task_id: str,
) -> dict:
    """Returns {"run": doc|None, "shared": bool}. run=None means the request
    stays pending for Front Desk - no run was created or joined."""
    if not start_time:
        return {"run": None, "shared": False}
    new_start = to_minutes(start_time)
    if new_start is None:
        return {"run": None, "shared": False}

    config = await get_scheduling_config()
    buffer_minutes = config.get("buffer_minutes", DEFAULT_BUFFER_MINUTES)
    window = (new_start - buffer_minutes, new_start + buffer_minutes)

    shareable = await _find_shareable_run(date, window, destination, buffer_minutes)
    if shareable:
        await db.transport_runs.update_one(
            {"run_id": shareable["run_id"]},
            {"$push": {"resident_task_ids": resident_task_id}, "$set": {"updated_at": now_utc().isoformat()}},
        )
        shareable["resident_task_ids"] = shareable.get("resident_task_ids", []) + [resident_task_id]
        return {"run": shareable, "shared": True}

    driver, vehicle = await find_free_resource_pair(date, window, buffer_minutes)
    if not driver or not vehicle:
        return {"run": None, "shared": False}

    run = TransportRun(
        date=date, depart_time=start_time, driver_id=driver["driver_id"], vehicle_id=vehicle["vehicle_id"],
        destination=destination, resident_task_ids=[resident_task_id],
    )
    doc = run.model_dump()
    doc["created_at"] = doc["created_at"].isoformat()
    doc["updated_at"] = doc["updated_at"].isoformat()
    await db.transport_runs.insert_one({**doc})
    doc.pop("_id", None)
    return {"run": doc, "shared": False}


async def release_task_from_run(run_id: Optional[str], task_id: str) -> None:
    if not run_id:
        return
    run = await db.transport_runs.find_one({"run_id": run_id}, {"_id": 0})
    if not run:
        return
    remaining = [t for t in run.get("resident_task_ids", []) if t != task_id]
    if remaining:
        await db.transport_runs.update_one({"run_id": run_id}, {"$set": {"resident_task_ids": remaining, "updated_at": now_utc().isoformat()}})
    else:
        await db.transport_runs.update_one({"run_id": run_id}, {"$set": {"status": "cancelled", "updated_at": now_utc().isoformat()}})
