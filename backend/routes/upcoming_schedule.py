"""Upcoming schedule (careops-therapy-upcoming-view-001).

A date-ordered view of planned, still-open requests - therapy appointments
first - for the department's staff and for the resident. It is a READ over
the canonical StaffTask rows (planned window = requested_for_date /
requested_for_time_label, the fields Plan and the detail dialog save), not a
calendar store: nothing is written, nothing is copied.

Ordering is facility-local day, then the planned time label parsed to
minutes ("9:30 AM" < "2:00 PM"; a label with no readable clock time sorts
after the timed ones that day), then creation time - so two reads return
the same order. Each row carries the details (provider / discipline /
location), the same lifecycle + spoken status the resident hears
(aria_request_status), and the linked ride's real facts (task_ride_link).
"""
from datetime import date, timedelta
from typing import Optional

from fastapi import APIRouter, Depends

from deps import db, get_current_user
from routes.aria_request_status import request_status_view
from routes.facility_local_time import facility_tz as _facility_tz
from routes.planned_time import UNTIMED, time_minutes  # noqa: F401  (re-exported for callers/tests)
from routes.realtime_facility import today_facility_date
from routes.resident_requests import OPEN_TASK_STATUSES, _resident_safe_view, _scope_query
from routes.tasks import _iso, staff_visibility_query
from routes.task_ride_link import _linked_ride, ride_summary

router = APIRouter(prefix="/tasks", tags=["tasks"])

MAX_DAYS = 60


def order_key(task: dict) -> tuple:
    created = task.get("created_at")
    created = created if isinstance(created, str) else (created.isoformat() if created else "")
    return (task.get("requested_for_date") or "", time_minutes(task.get("requested_for_time_label")), created, task.get("task_id") or "")


def window_query(days: int) -> dict:
    """Open requests planned from the facility's today through today+days. A
    ride that is linked to an appointment is not listed on its own: it is shown
    as the ride line of that appointment (a standalone ride still lists)."""
    days = max(0, min(int(days), MAX_DAYS))
    start = today_facility_date()
    end = (date.fromisoformat(start) + timedelta(days=days)).isoformat()
    return {"status": {"$in": OPEN_TASK_STATUSES}, "requested_for_date": {"$gte": start, "$lte": end},
            "linked_appointment_task_id": {"$in": [None, ""]}}


async def _ride(task: dict) -> Optional[dict]:
    ride = await _linked_ride(task)
    return await ride_summary(ride) if ride else None


@router.get("/upcoming")
async def upcoming_for_staff(department: Optional[str] = None, days: int = 14, limit: int = 200,
                             user=Depends(get_current_user)):
    """Staff: the department's planned open work, soonest first. Uses the SAME
    visibility rule as the task list (a staff member sees only their own
    department; owner/admin/front desk see all), narrowed to `department`
    when given."""
    q = window_query(days)
    q.update(staff_visibility_query(user))
    if department:
        if "visibility_role" in q and department not in q["visibility_role"].get("$in", [department]):
            return {"today": today_facility_date(), "days": days, "department": department, "items": []}
        q["visibility_role"] = department
    tz = await _facility_tz()
    rows = await db.staff_tasks.find(q, {"_id": 0}).to_list(max(1, min(limit, 500)))
    rows.sort(key=order_key)
    from routes.schedule_conflict import find_conflicts   # (imports this module; lazy to avoid the cycle)
    items = []
    for t in rows:
        view = request_status_view(t, tz)
        chk = await find_conflicts(t, t.get("requested_for_date"), t.get("requested_for_time_label"))
        items.append({**_iso(dict(t)), "lifecycle": view["lifecycle"], "spoken": view["spoken"], "ride": await _ride(t),
                      "conflicts": chk["conflicts"], "conflict_check": None if chk["checked"] else chk["reason"]})
    return {"today": today_facility_date(), "days": days, "department": department, "items": items}


@router.get("/resident-request/upcoming")
async def upcoming_for_resident(resident_id: Optional[str] = None, room: Optional[str] = None, days: int = 14):
    """Public (resident Home screen / Aria): the resident's own planned open
    requests, soonest first, in the resident-safe view plus the linked ride's
    real facts. Same scoping discipline as /resident-request/mine."""
    q = _scope_query(resident_id, room, None, allow_session=False)
    q.update(window_query(days))
    tz = await _facility_tz()
    rows = await db.staff_tasks.find(q, {"_id": 0}).to_list(100)
    rows.sort(key=order_key)
    return {"today": today_facility_date(), "days": max(0, min(int(days), MAX_DAYS)),
            "items": [{**_resident_safe_view(t, tz), "ride": await _ride(t)} for t in rows]}
