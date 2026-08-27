"""Resident-request-bus entry points (Terminal 8): the public, no-auth
routes Aria/the kiosk call to raise and check on a real request, plus
department email notification and re-request (duplicate) detection.

Split out of routes/tasks.py to stay under the repo's 400-line file cap -
this shares the same StaffTask/Receipt records tasks.py owns rather than
creating a parallel data model, and is mounted at the same /tasks prefix
so the public URLs (/api/tasks/resident-request, .../status) don't move.
"""
from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from models import StaffTask, TaskPriority, now_utc
from deps import db
from routes.receipts import create_receipt
from routes.notifications import notify_department
from routes.departments import get_active_departments
from routes.tasks import _resolve_denorms
from operational_provenance import reject_unconfirmed_time

router = APIRouter(prefix="/tasks", tags=["tasks"])

# Category names that predate the admin-managed Department list and don't
# match a department slug 1:1 - kept as fixed aliases so requests already
# built against these names keep working. Anything else must match a real
# Department.slug exactly (case-sensitive) - that's what makes a newly
# admin-added department (e.g. "therapy", "resident_programs") usable
# immediately with no code change.
CATEGORY_ALIASES: dict[str, str] = {"front_desk": "administration", "complaint": "administration"}


async def _resolve_visibility_role(category: str) -> Optional[str]:
    if category in CATEGORY_ALIASES:
        return CATEGORY_ALIASES[category]
    departments = await get_active_departments()
    if any(d["slug"] == category for d in departments):
        return category
    return None


async def get_request_categories() -> list[str]:
    """The live list of valid request_staff_help/check_request_status
    category values - every active department slug plus the fixed
    aliases. Imported by realtime_tools.py/realtime_aria_tools.py to
    build the tool schema's enum at session-mint time, so a newly
    admin-added department shows up for Aria immediately."""
    departments = await get_active_departments()
    return [d["slug"] for d in departments] + list(CATEGORY_ALIASES.keys())

# Statuses that mean a request is still open — used both to find the target
# of a re-request and to decide whether a new one is actually a duplicate.
OPEN_TASK_STATUSES = ["pending", "in_progress"]


class ResidentRequestInput(BaseModel):
    """Public — the resident-request-bus entry point Aria/the kiosk call.
    Deliberately narrow: no assigned_to, no arbitrary category, no title
    beyond what maps from category+resident_words. Category determines
    visibility_role server-side, never trusts a caller-supplied role."""
    category: str
    resident_id: Optional[str] = None
    room: Optional[str] = None
    resident_words: Optional[str] = None
    summary: str
    priority: TaskPriority = "normal"
    source: str = "aria_voice"  # "aria_voice" | "kiosk_button"
    conversation_session_id: Optional[str] = None


@router.post("/resident-request")
async def create_resident_request(data: ResidentRequestInput):
    """No auth - same public trust model as /alerts and the other
    resident-facing endpoints called from the kiosk during a live call.
    Creates a real StaffTask (so it appears in the existing, working staff
    task queue) plus a receipt, and returns enough for Aria to report
    truthfully: created, not "someone is on the way".

    If the same resident (or room, when there's no resident_id) already
    has an open request in this category, this does NOT spawn a second
    task - it re-uses the existing one, bumps re_request_count, and files
    a new receipt against it. That keeps one task = one operational item
    (no duplicate-queue clutter) while still giving Michael/staff a real,
    auditable trail of how many times it's been asked - the signal he
    uses to decide whether to bump priority."""
    visibility_role = await _resolve_visibility_role(data.category)
    if not visibility_role:
        raise HTTPException(status_code=400, detail=f"Unsupported request category: {data.category}")
    if data.source not in ("aria_voice", "kiosk_button"):
        raise HTTPException(status_code=400, detail="Invalid source")
    # 2026-08-23 (real, confirmed bug - Chauncey/Room 304): a fabricated
    # "10 o'clock" reached a live staff task. Reject rather than trust a
    # syntactically valid summary - see operational_provenance.py.
    rejection = await reject_unconfirmed_time(
        data.summary, resident_id=data.resident_id, conversation_session_id=data.conversation_session_id,
    )
    if rejection:
        raise HTTPException(status_code=422, detail={"needs_clarification": True, "field": "summary", "reason": rejection})

    dup_q: dict = {"category": data.category, "status": {"$in": OPEN_TASK_STATUSES}}
    if data.resident_id:
        dup_q["resident_id"] = data.resident_id
    elif data.room:
        dup_q["room"] = data.room
    else:
        dup_q = None  # nothing to dedup against (no resident/room on either side)

    existing = await db.staff_tasks.find_one(dup_q, {"_id": 0}, sort=[("created_at", -1)]) if dup_q else None

    if existing:
        # 2026-08-27 (real, confirmed bug - Room 401/Ellie): the old response
        # only said "duplicate" with no description of what the EXISTING open
        # ticket is actually about. When a resident's second, unrelated issue
        # in the same category (e.g. AC too warm) landed on top of an older
        # open one (e.g. a flickering reading lamp) - same dedup key is
        # category+resident, not the actual problem - Aria had no way to
        # know the two were different and told the resident "there's already
        # a maintenance request in progress for the AC", which was false: the
        # open request was about the lamp. Returning the existing ticket's own
        # summary lets the model describe it honestly instead of assuming it
        # matches what was just asked.
        same_issue = (existing.get("resident_words") or "").strip().lower() == (data.resident_words or data.summary or "").strip().lower()
        count = existing.get("re_request_count", 0) + 1
        now_iso = now_utc().isoformat()
        await db.staff_tasks.update_one(
            {"task_id": existing["task_id"]},
            {"$set": {"re_request_count": count, "last_re_requested_at": now_iso}},
        )
        receipt = await create_receipt(
            action_type="resident_request_re_requested", related_object_type="task",
            related_object_id=existing["task_id"], source=data.source,
            resident_id=data.resident_id, room=data.room,
            conversation_session_id=data.conversation_session_id, requested_by="resident",
            assigned_role=visibility_role,
        )
        await notify_department(
            visibility_role,
            f"CAOS Care: REPEAT request ({count}x) — {data.category}",
            f"Asked again (#{count}) — {data.summary}\n"
            f"Room: {data.room or 'unknown'}\n"
            f"Original request: {existing['created_at']}\n"
            f"This still hasn't been closed out.",
        )
        return {
            "task_id": existing["task_id"], "receipt_id": receipt["receipt_id"],
            "status": existing["status"], "duplicate": True, "re_request_count": count,
            "existing_summary": existing.get("resident_words") or existing.get("description") or existing.get("title"),
            "same_issue": same_issue,
            "scheduled_date": existing.get("requested_for_date"),
            "scheduled_time_label": existing.get("requested_for_time_label"),
        }

    payload = {
        "title": data.summary[:120],
        "description": data.summary,
        "category": data.category,
        "priority": data.priority,
        "source": data.source,
        "visibility_role": visibility_role,
        "resident_id": data.resident_id,
        "room": data.room,
        "resident_words": data.resident_words,
        "conversation_session_id": data.conversation_session_id,
    }
    await _resolve_denorms(payload)
    task = StaffTask(**payload)
    doc = task.model_dump()
    doc["created_at"] = doc["created_at"].isoformat()
    await db.staff_tasks.insert_one(doc)
    doc.pop("_id", None)
    receipt = await create_receipt(
        action_type="resident_request_created", related_object_type="task", related_object_id=doc["task_id"],
        source=data.source, resident_id=data.resident_id, room=data.room,
        conversation_session_id=data.conversation_session_id, requested_by="resident",
        assigned_role=visibility_role,
    )
    await notify_department(
        visibility_role,
        f"CAOS Care: new {data.category} request",
        f"{data.summary}\nRoom: {data.room or 'unknown'}\nPriority: {data.priority}",
    )
    return {"task_id": doc["task_id"], "receipt_id": receipt["receipt_id"], "status": doc["status"], "duplicate": False}


def _resident_safe_view(task: dict) -> dict:
    """The one place that decides what a resident/Aria is allowed to see of
    a StaffTask - used by both the single-status lookup and the list-mine
    endpoint below so a resident's screen and Aria's spoken answer can never
    drift apart (same underlying request state, same projection of it).
    Deliberately excludes internal-only fields (assigned_to user_id, source,
    visibility_role, etc.) - only what a resident/Aria should say out loud.
    """
    created_at = task["created_at"]
    return {
        "task_id": task["task_id"],
        "category": task["category"],
        # What the request is actually FOR - resident's own words when we
        # have them, falling back to the staff-facing title/description.
        # Previously this was never returned at all, so Aria had no way to
        # answer "what did I call maintenance about?"
        "what_for": task.get("resident_words") or task.get("description") or task.get("title") or "",
        "status": task["status"],
        "acknowledged": bool(task.get("acknowledged_at") or task["status"] in ("in_progress", "completed")),
        "assigned_to_name": task.get("assigned_name"),
        # Real staff-entered planned service window, or both None - never
        # invent an ETA when these are empty; the caller must say "no
        # scheduled time yet" in that case.
        "scheduled_date": task.get("requested_for_date"),
        "scheduled_time_label": task.get("requested_for_time_label"),
        # Latest staff-entered update (e.g. "waiting on a replacement part
        # from the vendor") - empty string if none, never fabricated.
        "latest_update": task.get("notes") or "",
        "re_request_count": task.get("re_request_count", 0),
        "created_at": created_at if isinstance(created_at, str) else created_at.isoformat(),
    }


@router.get("/resident-request/status")
async def resident_request_status(
    resident_id: Optional[str] = None,
    room: Optional[str] = None,
    conversation_session_id: Optional[str] = None,
    category: Optional[str] = None,
):
    """Public — lets Aria answer 'did anyone see my message?' truthfully.
    Returns the most recent matching request's real status, not a guess.
    Scoped to resident_id, or room, or (for Aria's own operator session,
    which has neither) conversation_session_id - so this can't be used to
    browse other residents'/sessions' requests."""
    q: dict = {"source": {"$in": ["aria_voice", "kiosk_button"]}}
    if resident_id:
        q["resident_id"] = resident_id
    elif room:
        q["room"] = room
    elif conversation_session_id:
        q["conversation_session_id"] = conversation_session_id
    else:
        raise HTTPException(status_code=400, detail="resident_id, room, or conversation_session_id required")
    if category:
        q["category"] = category
    task = await db.staff_tasks.find_one(q, {"_id": 0}, sort=[("created_at", -1)])
    if not task:
        return {"found": False}
    return {"found": True, **_resident_safe_view(task)}


@router.get("/resident-request/mine")
async def resident_request_mine(resident_id: Optional[str] = None, room: Optional[str] = None, limit: int = 8):
    """Public — the resident Home screen's Requests panel. Same scoping
    discipline as /status above (resident_id, else room - never a global
    'latest requests' query) but returns several recent ones instead of
    just the newest, so a resident with more than one open request sees all
    of them as separate cards, each with its own real status/schedule."""
    q: dict = {"source": {"$in": ["aria_voice", "kiosk_button"]}}
    if resident_id:
        q["resident_id"] = resident_id
    elif room:
        q["room"] = room
    else:
        raise HTTPException(status_code=400, detail="resident_id or room required")
    tasks = await db.staff_tasks.find(q, {"_id": 0}).sort("created_at", -1).to_list(max(1, min(limit, 30)))
    return [_resident_safe_view(t) for t in tasks]
