"""One simulated worker, as an owner sees them when clicking a name (#153 / #166).

Canonical tickets are the truth for what the worker did; the deterministic rota
supplies their schedule.  Nothing is invented: a state the simulator does not
model (breaks, physical location) is reported as unknown, never guessed.
"""
from collections import Counter

from simulation.community_dashboard_common import (
    default_store, planned_phase, scoped, sim_time, ticket_row, workflow_of,
)
from simulation.community_dashboard_view import HORIZON
from simulation.community_service_model import ROOM_SERVICE, meal_of
from simulation.community_shift_cover import active_cover
from simulation.community_staffing import (
    WEEKDAY_NAMES, WORKERS, _day_rota, weekday_of, worker_statuses,
)
from simulation.community_ticket_plan import COMPLETE
from simulation.community_ticket_text import routine_label

COMPLETED_LIMIT = 40
QUEUE_LIMIT = 15
HOUSEKEEPING_ZONES = {  # deterministic apartment assignment per housekeeper (owner 2026-10-15)
    "sim:staff:housekeeping:housekeeper:01": (1, 40),
    "sim:staff:housekeeping:housekeeper:02": (41, 80),
}
STATE_LABELS = {
    "working": "On duty · working a ticket", "free": "On duty · free",
    "on_call": "On call (off site)", "called_in": "Called in from on call · working",
    "off_duty": "Off duty", "covered": "Shift covered by a real staff member",
}


class WorkerNotFound(LookupError):
    """The id is not one of this community's simulated workers."""


def worker_state(duty: str, holding: bool, covered: bool) -> str:
    if covered:
        return "covered"
    if duty == "on_duty":
        return "working" if holding else "free"
    if duty == "on_call":
        return "called_in" if holding else "on_call"
    return "off_duty"


def weekly_schedule(actor_id: str, day: int) -> list[dict]:
    """The worker's duties for the seven days starting ``day`` (rota truth, planned)."""
    rows = []
    for offset in range(7):
        on = day + offset
        if on >= HORIZON // 1440:
            break
        for row in _day_rota(on):
            if row["actor_id"] == actor_id:
                rows.append({"day": on + 1, "weekday": WEEKDAY_NAMES[weekday_of(on)], "shift": row["shift"],
                             "start": row["start"], "end": row["end"], "duty": row["duty"]})
    return rows


def _finished_day(task: dict, plan: dict):
    done = planned_phase(plan, workflow_of(task), COMPLETE)
    return None if done is None else done.day_index


def _role_details(worker: dict, current: list, today: list) -> dict:
    """What matters for this role, from the same canonical tickets."""
    role, department = worker["job_role"], worker["department"]
    if department == "kitchen":
        if role == "cook":
            return {"kind": "cook", "note": "Prep, plating and dish work are the cook's shift; "
                                            "they are not individual tickets."}
        meals = Counter()
        for row in today:
            meal = meal_of(row["routine"] or "")
            if meal and row["status"] == "completed":
                where = "apartment" if (row["routine"] or "").endswith(ROOM_SERVICE) else "dining room"
                meals[f"{meal} · {where}"] += 1
        working = current[0] if current else None
        return {"kind": "meal_service",
                "current_service": routine_label(working["routine"]) if working and working["routine"] else None,
                "served_today": dict(sorted(meals.items()))}
    if department == "housekeeping":
        first, last = HOUSEKEEPING_ZONES.get(worker["actor_id"], (None, None))
        return {"kind": "housekeeping",
                "assigned_rooms": None if first is None else f"SIM-{first:03d} to SIM-{last:03d}",
                "note": "Zone assignment only; housekeeping tickets still go to whichever housekeeper "
                        "is free (the housekeeping workload is not yet redesigned)."}
    if department == "transportation":
        return {"kind": "transportation", "rides_today": [row["task_id"] for row in today]}
    if department == "nursing":
        residents = sorted({row["resident"]["name"] or row["resident"]["id"] for row in today + current})
        return {"kind": "resident_care", "residents_today": residents}
    if department == "maintenance":
        return {"kind": "maintenance_queue"}  # filled by the caller from the department queue
    return {"kind": "general"}


async def worker_detail(actor_id: str, *, run: dict, as_of: int, plan: dict, store=None) -> dict:
    worker = next((row for row in WORKERS if row["actor_id"] == actor_id), None)
    if worker is None:
        raise WorkerNotFound(f"unknown simulated worker {actor_id}")
    store = store if store is not None else default_store()
    at = min(as_of, HORIZON - 1)
    day = at // 1440
    status = next(row for row in worker_statuses(day, at % 1440) if row["actor_id"] == actor_id)
    mine = await store.staff_tasks.find(
        {**scoped(run["run_id"]), "simulated": True, "assigned_to": actor_id},
        {"_id": 0}).to_list(None)
    rows = [(task, ticket_row(task, plan, as_of)) for task in mine]
    current = [row for task, row in rows if row["status"] == "in_progress"]
    today = [row for task, row in rows if (row["requested"] or {}).get("day") == day + 1]
    completed = [(task, row) for task, row in rows if row["status"] == "completed"]
    completed_today = [row for task, row in completed if _finished_day(task, plan) == day]
    cover = await active_cover(store, run["run_id"], actor_id)
    state = worker_state(status["status"], bool(current), bool(cover))
    details = _role_details(worker, current, today)
    if details["kind"] == "maintenance_queue":
        pending = await store.staff_tasks.find(
            {**scoped(run["run_id"]), "simulated": True, "category": "maintenance", "status": "pending"},
            {"_id": 0}).to_list(None)
        queue = sorted((ticket_row(t, plan, as_of) for t in pending),
                       key=lambda r: (r["requested"] or {}).get("absolute_minute") or 0)
        details.update({"open_queue_total": len(queue), "open_queue": queue[:QUEUE_LIMIT]})
    newest = sorted((row for _task, row in completed),
                    key=lambda r: -((r["requested"] or {}).get("absolute_minute") or 0))
    return {
        "worker": {k: worker[k] for k in ("actor_id", "name", "job_role", "department",
                                          "department_label", "actor_type", "identity_basis")},
        "simulated": worker["actor_id"].startswith("sim:staff:"),
        "duty": status["status"], "shift_now": status["shift"],
        "state": state, "state_label": STATE_LABELS[state],
        "on_break": None,  # breaks are not modelled: unknown, never assumed
        "location": None,  # physical location is not modelled: unknown
        "covered_by": (cover or {}).get("covered_by_name"),
        "week": weekly_schedule(actor_id, day),
        "current": current,
        "today": {"day": day + 1, "weekday": WEEKDAY_NAMES[weekday_of(day)],
                  "assigned": today, "assigned_total": len(today),
                  "completed_total": len(completed_today)},
        "role_details": details,
        "completed_total": len(completed),
        "completed": newest[:COMPLETED_LIMIT],
        "as_of_minute": sim_time(as_of),
    }
