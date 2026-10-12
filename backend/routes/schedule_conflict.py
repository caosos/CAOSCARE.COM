"""Planned-window conflicts (careops-therapy-conflict-001).

Two planned, still-open requests for the SAME resident on the SAME facility
day overlap when their slots intersect. The slot is one bounded operational
duration (SLOT_MINUTES, default 60, env CAOSCARE_PLAN_SLOT_MINUTES) starting
at the planned time label parsed exactly as the upcoming view parses it
(upcoming_schedule.time_minutes). There is no per-task duration field and no
calendar store: this is a read over the canonical planned fields.

Honesty: a label with no readable clock time ("afternoon") cannot be checked.
The result then says `checked: False` with the reason, never "no conflict";
other requests whose label is unreadable are listed as `undetermined`.

Staff double-booking (careops-therapy-staff-conflict-001): the same window is
also checked against OTHER residents' open planned requests in the same
department that share this request's provider (provider_name, compared without
case or extra spaces) or its assignee. Those come back with kind "staff" and
what they share; same-resident overlaps have kind "resident". Staff views only:
the resident's own views never carry conflicts.

Enforcement lives in the PATCH route: an overlapping window is refused (409,
conflicts in the detail) unless the body says `conflict_override: true`; the
schedule receipt then records the override and the conflicting request ids.
"""
import os
from typing import Optional

from fastapi import APIRouter, Depends

from deps import db, get_current_user
from routes.actor_context import actor_from_user
from routes.task_lifecycle import LifecycleError, authority_for, load
from routes.planned_time import UNTIMED, time_minutes

router = APIRouter(prefix="/tasks", tags=["tasks"])
OPEN_TASK_STATUSES = ("pending", "in_progress")   # same two values resident_requests.OPEN_TASK_STATUSES names
SLOT_MINUTES = max(5, int(os.getenv("CAOSCARE_PLAN_SLOT_MINUTES", "60")))
UNREADABLE = "the planned time can't be read as a clock time, so overlap was not checked"


def _norm(name) -> str:
    return " ".join(str(name or "").split()).casefold()


def _brief(t: dict, kind: str = "resident", shared: Optional[str] = None) -> dict:
    return {"task_id": t["task_id"], "kind": kind, "shared": shared, "resident_id": t.get("resident_id"),
            "room": t.get("room"), "category": t.get("category"), "status": t.get("status"),
            "what": t.get("resident_words") or t.get("description") or t.get("title") or "",
            "requested_for_date": t.get("requested_for_date"), "requested_for_time_label": t.get("requested_for_time_label"),
            "provider_name": t.get("provider_name"), "location": t.get("location")}


async def find_conflicts(task: dict, date: Optional[str], label: Optional[str]) -> dict:
    """Overlaps for `task` if it were planned at (date, label). Reads the
    resident's other OPEN planned requests on that day; never writes."""
    out = {"checked": False, "reason": None, "slot_minutes": SLOT_MINUTES, "conflicts": [], "undetermined": []}
    provider, assignee = _norm(task.get("provider_name")), task.get("assigned_to")
    if not date or not (task.get("resident_id") or provider or assignee):
        out["reason"] = "no planned date" if not date else "no resident, provider or assignee to check"
        return out
    start = time_minutes(label)
    if start == UNTIMED:
        out["reason"] = UNREADABLE
        return out
    others = []
    if task.get("resident_id"):
        others = await db.staff_tasks.find({"resident_id": task["resident_id"], "requested_for_date": date,
                                            "status": {"$in": OPEN_TASK_STATUSES}, "task_id": {"$ne": task["task_id"]}},
                                           {"_id": 0}).to_list(50)
    end = start + SLOT_MINUTES
    out["checked"] = True
    for o in await _staff_overlaps(task, date, provider, assignee):
        s2 = time_minutes(o["t"].get("requested_for_time_label"))
        if s2 != UNTIMED and s2 < end and start < s2 + SLOT_MINUTES:
            out["conflicts"].append(_brief(o["t"], "staff", o["shared"]))
    for o in others:
        # A ride linked to an appointment is that appointment's transport, not a second
        # commitment: the appointment itself is what overlaps (its own ride line shows the
        # ride). A standalone ride (no appointment) still counts.
        if o.get("linked_appointment_task_id") or task.get("linked_ride_task_id") == o["task_id"]:
            continue
        s2 = time_minutes(o.get("requested_for_time_label"))
        if s2 == UNTIMED:
            out["undetermined"].append(_brief(o))
        elif s2 < end and start < s2 + SLOT_MINUTES:
            out["conflicts"].append(_brief(o))
    return out


async def _staff_overlaps(task: dict, date: str, provider: str, assignee: Optional[str]) -> list:
    """Other residents' open planned requests that day, in the same department,
    with the same provider or assignee. Timing is filtered by the caller."""
    if not (provider or assignee) or not task.get("visibility_role"):
        return []
    q = {"requested_for_date": date, "status": {"$in": OPEN_TASK_STATUSES}, "task_id": {"$ne": task["task_id"]},
         "visibility_role": task["visibility_role"]}
    if task.get("resident_id"):
        q["resident_id"] = {"$ne": task["resident_id"]}
    out = []
    for o in await db.staff_tasks.find(q, {"_id": 0}).to_list(200):
        if o.get("linked_appointment_task_id"):
            continue
        if provider and _norm(o.get("provider_name")) == provider:
            out.append({"t": o, "shared": f"provider {o.get('provider_name')}"})
        elif assignee and o.get("assigned_to") == assignee:
            out.append({"t": o, "shared": f"assigned to {o.get('assigned_to_name') or o.get('assigned_name') or 'the same staff member'}"})
    return out


@router.get("/{task_id}/conflicts")
async def conflicts_for(task_id: str, requested_for_date: Optional[str] = None,
                        requested_for_time_label: Optional[str] = None, user=Depends(get_current_user)):
    """What would overlap if this request were planned at the given window
    (defaults to its current one). Same authority as the other read views."""
    task = await load(task_id)
    if not authority_for(task, actor_from_user(user), user):
        raise LifecycleError(403, "Not allowed to see this request")
    return await find_conflicts(task, requested_for_date or task.get("requested_for_date"),
                                requested_for_time_label if requested_for_time_label is not None else task.get("requested_for_time_label"))
