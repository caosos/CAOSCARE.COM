"""Drill-in read models for the Live Operations dashboard (SIM-007A).

Department, worker and resident detail.  Canonical tickets are the truth for
what happened; the deterministic rota and plan supply schedules and
*upcoming* work, always labelled as planned, never as done.
"""
from typing import Optional

from simulation.community_dashboard_common import (
    TASK_FIELDS, current_run, default_store, plan_events, scoped, sim_time, ticket_row,
)
from simulation.community_dashboard_view import HORIZON, executed_position
from simulation.community_day_queue import build_day_queue
from simulation import community_worker_detail
from simulation.community_shift_cover import active_cover
from simulation.community_staffing import DEPARTMENT_LABELS, WORKERS, _day_rota, worker_statuses
from simulation.community_ticket_plan import CLAIM, OPEN
from simulation.community_ticket_text import routine_label

COMPLETED_LIMIT = 40


class DashboardNotFound(LookupError):
    """The requested department, worker or resident is not part of this run."""


def _shift(row: dict, day: int) -> dict:
    start = day * 1440 + row["start_minute"]
    end = day * 1440 + row["end_minute"] + (1440 if row["spans_midnight"] else 0)
    return {"actor_id": row["actor_id"], "name": row["name"], "job_role": row["job_role"],
            "shift": row["shift"], "duty": row["duty"], "start": sim_time(start), "end": sim_time(end)}


def _shifts(day: int, *, department: Optional[str] = None, actor_id: Optional[str] = None) -> list:
    """Shifts touching this day, including overnight shifts carried over from yesterday."""
    def wanted(row):
        return ((department is None or row["department"] == department)
                and (actor_id is None or row["actor_id"] == actor_id))
    carried = [_shift(row, day - 1) for row in _day_rota(day - 1) if row["spans_midnight"] and wanted(row)]
    rows = carried + [_shift(row, day) for row in _day_rota(day) if wanted(row)]
    return sorted(rows, key=lambda row: (row["start"]["absolute_minute"], row["name"]))


async def _context(store):
    run = await current_run(store)
    if run is None:
        raise DashboardNotFound("no living-community run exists")
    as_of = executed_position(run)
    return run, as_of, plan_events(run.get("plan_revision") or "")


async def _tasks(store, run_id: str, query: dict, *, limit=None, newest=False) -> list[dict]:
    cursor = store.staff_tasks.find({**scoped(run_id), "simulated": True, **query}, TASK_FIELDS)
    if newest:
        cursor = cursor.sort("completed_at", -1)
    return await cursor.to_list(limit)


def _planned(run: dict, as_of: int, *, department=None, actor_id=None, resident_id=None,
             phase=OPEN, limit=25, days=1) -> list[dict]:
    """Upcoming planned events from now through the next ``days`` days (not yet executed)."""
    rows = []
    today = as_of // 1440
    for day in range(max(0, today - 1), today + days):  # yesterday's plan can roll into today
        if day >= 90:
            continue
        for event in build_day_queue(day, cohort=run.get("cohort") or "community_75"):
            minute = event.day_index * 1440 + event.minute
            if (event.task_phase != phase or minute <= as_of or minute // 1440 >= today + days
                    or (department and event.department != department)
                    or (actor_id and event.actor_id != actor_id)
                    or (resident_id and event.target_id != resident_id)):
                continue
            rows.append({"routine": event.action_type, "label": routine_label(event.action_type),
                         "department": event.department,
                         "at": sim_time(minute), "resident_id": event.target_id,
                         "worker": event.actor_name if phase != OPEN else None, "planned": True})
    rows.sort(key=lambda row: row["at"]["absolute_minute"])
    return rows[:limit]


async def department_detail(slug: str, *, store=None) -> dict:
    if slug not in DEPARTMENT_LABELS:
        raise DashboardNotFound(f"unknown department {slug}")
    store = store if store is not None else default_store()
    run, as_of, plan = await _context(store)
    day = min(as_of, HORIZON - 1) // 1440
    statuses = [row for row in worker_statuses(day, min(as_of, HORIZON - 1) % 1440)
                if row["department"] == slug]
    open_rows = [ticket_row(t, plan, as_of) for t in await _tasks(
        store, run["run_id"], {"category": slug, "status": {"$in": ["pending", "in_progress"]}})]
    done = [ticket_row(t, plan, as_of) for t in await _tasks(
        store, run["run_id"], {"category": slug, "status": "completed",
                               "conversation_session_id": {"$regex": f"^simulator:event:day-{day:03d}:"}},
        limit=COMPLETED_LIMIT, newest=True)]
    holding = {row["worker"]["id"]: row for row in open_rows if row["status"] == "in_progress"}
    people = []
    for row in statuses:
        cover = await active_cover(store, run["run_id"], row["actor_id"])
        people.append({**{k: row[k] for k in ("actor_id", "name", "job_role", "shift")},
                       "duty": row["status"], "covered_by": (cover or {}).get("covered_by_name"),
                       "current": holding.get(row["actor_id"]),
                       "today": _shifts(day, actor_id=row["actor_id"])})
    waiting = sorted((r for r in open_rows if r["status"] == "pending"),
                     key=lambda r: -(r["waiting_minutes"] or 0))
    return {
        "status": "loaded", "slug": slug, "label": DEPARTMENT_LABELS[slug],
        "run_id": run["run_id"], "as_of": sim_time(as_of), "day": day + 1,
        "people": people, "schedule_today": _shifts(day, department=slug),
        "work": {"waiting": waiting, "overdue": [r for r in waiting if r["overdue"]],
                 "in_progress": [r for r in open_rows if r["status"] == "in_progress"],
                 "completed_today": done,
                 "upcoming": _planned(run, as_of, department=slug)},
    }


async def worker_detail(actor_id: str, *, store=None) -> dict:
    store = store if store is not None else default_store()
    if not any(row["actor_id"] == actor_id for row in WORKERS):
        raise DashboardNotFound(f"unknown simulated worker {actor_id}")
    run, as_of, plan = await _context(store)
    day = min(as_of, HORIZON - 1) // 1440
    detail = await community_worker_detail.worker_detail(actor_id, run=run, as_of=as_of, plan=plan, store=store)
    return {
        "status": "loaded", "run_id": run["run_id"], "as_of": sim_time(as_of), **detail,
        "schedule": {"today": _shifts(day, actor_id=actor_id),
                     "tomorrow": _shifts(day + 1, actor_id=actor_id) if day + 1 < 90 else []},
        "next_planned": _planned(run, as_of, actor_id=actor_id, phase=CLAIM, limit=10, days=2),
    }


async def resident_detail(resident_id: str, *, store=None) -> dict:
    store = store if store is not None else default_store()
    run, as_of, plan = await _context(store)
    profile = await store.residents.find_one(
        {"resident_id": resident_id, "simulation_scope": scoped(run["run_id"])["simulation_scope"]},
        {"_id": 0, "resident_id": 1, "name": 1, "preferred_name": 1, "room": 1, "occupant_slot": 1,
         "participation_level": 1, "preferences": 1, "synthetic": 1, "date_of_birth": 1})
    if profile is None:
        raise DashboardNotFound(f"unknown simulated resident {resident_id}")
    tasks = await _tasks(store, run["run_id"], {"resident_id": resident_id})
    rows = sorted((ticket_row(t, plan, as_of) for t in tasks),
                  key=lambda r: -((r["requested"] or {}).get("absolute_minute") or 0))
    day = min(as_of, HORIZON - 1) // 1440
    today = [r for r in rows if (r["requested"] or {}).get("day") == day + 1]
    return {
        "status": "loaded", "run_id": run["run_id"], "as_of": sim_time(as_of),
        "profile": profile,
        "care_today": {"done_or_open": today,
                       "upcoming": _planned(run, as_of, resident_id=resident_id)},
        "requests": {"waiting": [r for r in rows if r["status"] == "pending"],
                     "in_progress": [r for r in rows if r["status"] == "in_progress"],
                     "completed": [r for r in rows if r["status"] == "completed"][:COMPLETED_LIMIT],
                     "completed_total": sum(r["status"] == "completed" for r in rows)},
    }
