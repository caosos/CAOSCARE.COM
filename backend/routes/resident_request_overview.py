"""All of a resident's open requests in one read (RQ-032 status breadth),
so "did anyone see my requests?" is answered across nursing, maintenance,
front desk and every other department at once instead of one category per
call. Same scoping and the same resident-safe view as /resident-request/
status - no second wording or lifecycle."""
from typing import Optional

from fastapi import APIRouter

from deps import db
from routes.facility_local_time import facility_tz as _facility_tz
from routes.resident_requests import OPEN_TASK_STATUSES, _resident_safe_view, _scope_query

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.get("/resident-request/open")
async def resident_requests_open(
    resident_id: Optional[str] = None,
    room: Optional[str] = None,
    conversation_session_id: Optional[str] = None,
    exclude_category: Optional[str] = None,
    limit: int = 10,
):
    """Public - every genuinely open request for the resident (oldest first),
    each with its own truthful state. `exclude_category` lets the caller
    cover a category (transportation) from its own richer status view."""
    q = _scope_query(resident_id, room, conversation_session_id)
    q["status"] = {"$in": OPEN_TASK_STATUSES}
    if exclude_category:
        q["category"] = {"$ne": exclude_category}
    tz = await _facility_tz()
    tasks = await db.staff_tasks.find(q, {"_id": 0}).sort("created_at", 1).to_list(max(1, min(limit, 20)))
    return {"found": bool(tasks), "scope": "current", "requests": [_resident_safe_view(t, tz) for t in tasks]}
