"""Resident-request-bus entry points (Terminal 8): the public, no-auth
routes Aria/the kiosk call to raise and check on a real request (plus one
authenticated source, "front_desk", added 2026-09-21 - see
create_resident_request's own docstring), department email notification,
and re-request (duplicate) detection.

Split out of routes/tasks.py to stay under the repo's 400-line file cap -
this shares the same StaffTask/Receipt records tasks.py owns rather than
creating a parallel data model, and is mounted at the same /tasks prefix
so the public URLs (/api/tasks/resident-request, .../status) don't move.
"""
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from models import RESIDENT_ORIGIN_SOURCES, StaffTask, TaskPriority, now_utc
from deps import db, get_current_user
from routes import task_lifecycle
from routes.actor_context import actor_from_user, actor_resident_claim
from routes.task_history import task_event, latest_note_at, times_asked
from routes.task_lifecycle import simulation_marker
from routes.notifications import notify_department, simulation_of
from routes.departments import get_active_departments
from routes.facility_local_time import facility_tz as _facility_tz, facility_local as _facility_local
from routes.tasks import _resolve_denorms
from routes.aria_request_status import request_status_view
from operational_provenance import reject_unconfirmed_time

router = APIRouter(prefix="/tasks", tags=["tasks"])

# Closed = no longer an operational concern. Queryable only via the
# explicit /history path, never surfaced as "current".
CLOSED_TASK_STATUSES = ["completed", "skipped"]

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
    source: str = "aria_voice"  # "aria_voice" | "kiosk_button" | "front_desk" (auth required for front_desk)
    conversation_session_id: Optional[str] = None


async def create_resident_request(data: ResidentRequestInput, *, user: Optional[dict] = None,
                                  simulation_run_id: Optional[str] = None) -> dict:
    """Public (no auth) for "aria_voice"/"kiosk_button" - same trust model
    as /alerts and the other resident-facing endpoints called from the
    kiosk during a live call. Creates a real StaffTask (so it appears in
    the existing, working staff task queue) plus a receipt, and returns
    enough for Aria to report truthfully: created, not "someone is on the
    way".

    "front_desk" is the one other allowed source, and it is NOT public -
    `user` must be an already-authenticated caller (owner/admin/staff/
    front_desk role) resolved by the thin HTTP route wrapper below from a
    real Request via get_current_user - the same auth every other
    authenticated route in this app already uses, not a new mechanism,
    and not a weakening of the public sources' own trust model, which is
    untouched. Taking an already-resolved `user` dict here (never a
    Request) keeps this function directly callable in-process - by tests,
    or a future simulator per ENGINEERING_CONTRACT.md decision 1 - without
    needing to fabricate an HTTP Request object. This is the Track 1 reuse
    point (audit §12): a human-entered request goes through the exact same
    dedup/receipt/notification/lifecycle-speaking logic below as a
    resident-originated one, instead of the plain POST /tasks path
    (tasks.py::create_task), which has no duplicate-detection at all.

    If the same resident (or room, when there's no resident_id) already
    has an open request in this category, this does NOT spawn a second
    task - it re-uses the existing one, bumps re_request_count, and files
    a new receipt against it. That keeps one task = one operational item
    (no duplicate-queue clutter) while still giving Michael/staff a real,
    auditable trail of how many times it's been asked - the signal he
    uses to decide whether to bump priority.

    `simulation_run_id` (SC-17): in-process simulator only, never from a
    request body. Needs a real run and a synthetic resident; records source/
    channel "simulator" + the run id; notifications stay simulated (SC-16)."""
    visibility_role = await _resolve_visibility_role(data.category)
    if not visibility_role:
        raise HTTPException(status_code=400, detail=f"Unsupported request category: {data.category}")
    marker = await simulation_marker(data.resident_id, simulation_run_id)
    source = data.source
    if simulation_run_id:
        if not marker:
            raise HTTPException(status_code=400, detail="A simulation run may only raise requests for a synthetic resident")
        if not await db.sim_runs.find_one({"run_id": simulation_run_id}, {"_id": 1}):
            raise HTTPException(status_code=400, detail=f"Unknown simulation run {simulation_run_id}")
        source = "simulator"
        actor = actor_resident_claim(data.resident_id, data.room, "simulator", synthetic=True)
        authority = "simulation_run"
    elif data.source == "front_desk":
        if not user or user.get("role") not in ("owner", "admin", "staff", "front_desk"):
            raise HTTPException(status_code=403, detail="Not authorized to create resident requests")
        actor, authority = actor_from_user(user, channel="front_desk"), "front_desk_entry"
    elif data.source in ("aria_voice", "kiosk_button"):
        # The room is known; who spoke is a claim, not a verified identity (D3).
        actor = actor_resident_claim(data.resident_id, data.room, data.source, synthetic=bool(marker))
        authority = "public_resident_bus"
    else:
        raise HTTPException(status_code=400, detail="Invalid source")
    # 2026-08-23 (real, confirmed bug - Chauncey/Room 304): a fabricated
    # "10 o'clock" reached a live staff task. Reject rather than trust a
    # syntactically valid summary - see operational_provenance.py. The check
    # guards times a model might invent; a time typed by an authenticated
    # front-desk user (e.g. a callback time) is staff-entered fact (SC-7).
    rejection = None if data.source == "front_desk" else await reject_unconfirmed_time(
        data.summary, resident_id=data.resident_id, conversation_session_id=data.conversation_session_id,
    )
    if rejection:
        raise HTTPException(status_code=422, detail={"needs_clarification": True, "field": "summary", "reason": rejection})

    # A run's requests dedup only within that run (SC-17).
    dup_q: dict = {"category": data.category, "status": {"$in": OPEN_TASK_STATUSES},
                   "simulation_run_id": simulation_run_id}
    if data.resident_id:
        dup_q["resident_id"] = data.resident_id
    elif data.room:
        dup_q["room"] = data.room
    else:
        dup_q = None  # nothing to dedup against (no resident/room on either side)

    existing = await db.staff_tasks.find_one(dup_q, {"_id": 0}, sort=[("created_at", -1)]) if dup_q else None
    words = data.resident_words or data.summary
    if existing:
        # The repeat ask is a state change on the open request, so it goes
        # through the lifecycle (chained receipt). A legacy request with no
        # recorded origin refuses the change (and records that, D5); the
        # resident's ask is then filed as a new request rather than lost (D3).
        try:
            existing, receipt = await task_lifecycle.transition(
                existing["task_id"], actor, user, action="re_request", authority=authority,
                action_type="resident_request_re_requested", status="created",
                build=lambda t, rid: (
                    {"re_request_count": t.get("re_request_count", 0) + 1,
                     "last_re_requested_at": now_utc().isoformat()},
                    [task_event("re_request", to=t.get("re_request_count", 0) + 1, by=actor.actor_id,
                                by_name=actor.name or "resident", text=words, receipt_id=rid)]))
        except task_lifecycle.LifecycleError as e:
            if e.status_code != 409:
                raise
            existing = None

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
        count = existing.get("re_request_count", 0)
        asked = times_asked({"re_request_count": count})
        await notify_department(
            visibility_role,
            f"CAOS Care: REPEAT request (asked {asked}x) — {data.category}",
            f"Asked {asked} times now — {data.summary}\n"
            f"Room: {data.room or 'unknown'}\n"
            f"Original request: {existing['created_at']}\n"
            f"This still hasn't been closed out.",
            simulation=simulation_of(existing, receipt["receipt_id"]),
        )
        # Speak the duplicate from Layer E's lifecycle vocabulary + real age,
        # so it cannot contradict "What's actually happening right now".
        auth = request_status_view(existing, await _facility_tz())
        return {
            "task_id": existing["task_id"], "receipt_id": receipt["receipt_id"],
            "status": existing["status"], "duplicate": True, "re_request_count": count,
            "times_asked": asked,
            "existing_summary": existing.get("resident_words") or existing.get("description") or existing.get("title"),
            "same_issue": same_issue,
            "scheduled_date": existing.get("requested_for_date"),
            "scheduled_time_label": existing.get("requested_for_time_label"),
            "lifecycle": auth["lifecycle"], "opened_age": auth["opened_age"],
            "spoken": auth["spoken"],
        }

    payload = {
        "title": data.summary[:120],
        "description": data.summary,
        "category": data.category,
        "priority": data.priority,
        "source": source,
        "visibility_role": visibility_role,
        "resident_id": data.resident_id,
        "room": data.room,
        "resident_words": data.resident_words,
        "conversation_session_id": data.conversation_session_id,
        **marker,
    }
    await _resolve_denorms(payload)
    task = StaffTask(**payload)
    doc = task.model_dump()
    doc["created_at"] = doc["created_at"].isoformat()
    await db.staff_tasks.insert_one(doc)
    doc.pop("_id", None)
    receipt = await task_lifecycle.record_origin(doc, actor, action_type="resident_request_created",
                                                 authority=authority)
    await notify_department(
        visibility_role,
        f"CAOS Care: new {data.category} request",
        f"{data.summary}\nRoom: {data.room or 'unknown'}\nPriority: {data.priority}",
        simulation=simulation_of(doc, receipt["receipt_id"]),
    )
    return {"task_id": doc["task_id"], "receipt_id": receipt["receipt_id"], "status": doc["status"], "duplicate": False}


@router.post("/resident-request")
async def resident_request_endpoint(data: ResidentRequestInput, request: Request):
    """Thin HTTP wrapper - the only place a real Request/get_current_user
    is touched. Resolves the caller ONLY for the one non-public source
    (front_desk); aria_voice/kiosk_button never authenticate, preserving
    the existing public trust model exactly."""
    user = await get_current_user(request) if data.source == "front_desk" else None
    return await create_resident_request(data, user=user)


def _iso(v) -> Optional[str]:
    if v is None:
        return None
    return v if isinstance(v, str) else v.isoformat()


def _resident_safe_view(task: dict, tz: str) -> dict:
    """The one place that decides what a resident/Aria is allowed to see of
    a StaffTask - used by the current-status lookup, the history lookup and
    the list-mine endpoint so a resident's screen and Aria's spoken answer
    can never drift apart. Excludes internal-only fields (assigned_to
    user_id, source, visibility_role, completed_by user_id, ...).

    Every lifecycle timestamp that ACTUALLY EXISTS on StaffTask is exposed
    here as {iso, local, label}; one that does not exist / was never set is
    null (Aria says "I don't have that", never invents one).
    `latest_update` is the latest staff note; `latest_update_at` is when it
    was written, from the task's event_log (null for notes written before
    event_log existed).
    """
    status = task["status"]
    is_open = status in OPEN_TASK_STATUSES
    created = _iso(task.get("created_at"))
    ack = _iso(task.get("acknowledged_at"))
    started = _iso(task.get("started_at"))
    completed = _iso(task.get("completed_at"))
    last_re = _iso(task.get("last_re_requested_at"))
    note_at = latest_note_at(task)
    return {
        "task_id": task["task_id"],
        "category": task["category"],
        "what_for": task.get("resident_words") or task.get("description") or task.get("title") or "",
        "status": status,
        "is_open": is_open,               # the operational current-vs-closed answer
        "acknowledged": request_status_view(task)["lifecycle"] != "open",
        "assigned_to_name": task.get("assigned_name"),
        "completed_by_name": task.get("completed_by_name"),
        "scheduled_date": task.get("requested_for_date"),        # planned service window,
        "scheduled_time_label": task.get("requested_for_time_label"),  # separate from lifecycle
        "latest_update": task.get("notes") or "",
        "latest_update_at": _facility_local(note_at, tz),
        "re_request_count": task.get("re_request_count", 0),
        "times_asked": times_asked(task),
        # ---- authoritative lifecycle timestamps (UTC iso + facility-local) ----
        "created_at": created,            # raw UTC kept for back-compat / audit
        "created": _facility_local(created, tz),
        "acknowledged_at": _facility_local(ack, tz),
        "started_at": _facility_local(started, tz),
        "completed_at": _facility_local(completed, tz),
        "last_re_requested_at": _facility_local(last_re, tz),
        # Layer-E-consistent lifecycle + a ready-to-speak sentence. `status`
        # (raw) is kept above for back-compat; `lifecycle`/`spoken` are what
        # a truthful tool result should use.
        **request_status_view(task, tz),
    }


def _scope_query(resident_id, room, conversation_session_id, allow_session: bool = True) -> dict:
    q: dict = {"source": {"$in": list(RESIDENT_ORIGIN_SOURCES)}}
    if resident_id:
        q["resident_id"] = resident_id
    elif room:
        q["room"] = room
    elif allow_session and conversation_session_id:
        q["conversation_session_id"] = conversation_session_id
    else:
        raise HTTPException(
            status_code=400,
            detail="resident_id, room" + (", or conversation_session_id" if allow_session else "") + " required",
        )
    return q


@router.get("/resident-request/status")
async def resident_request_status(
    resident_id: Optional[str] = None,
    room: Optional[str] = None,
    conversation_session_id: Optional[str] = None,
    category: Optional[str] = None,
):
    """Public — the resident's CURRENT (open) request status. CURRENT STATE
    and HISTORY are different things: this endpoint returns ONLY a
    genuinely open request (status pending / in_progress). A completed,
    resolved, or skipped request is NOT current and is never returned here
    - it stays queryable via /resident-request/history when the resident
    explicitly asks about the past. `found: false` here means "nothing open
    right now", not "no such request ever existed".

    Scoped to resident_id, or room, or (Aria's own operator session, which
    has neither) conversation_session_id - never a cross-resident browse."""
    q = _scope_query(resident_id, room, conversation_session_id)
    q["status"] = {"$in": OPEN_TASK_STATUSES}
    if category:
        q["category"] = category
    task = await db.staff_tasks.find_one(q, {"_id": 0}, sort=[("created_at", -1)])
    if not task:
        return {"found": False, "scope": "current"}
    return {"found": True, "scope": "current", **_resident_safe_view(task, await _facility_tz())}


@router.get("/resident-request/history")
async def resident_request_history(
    resident_id: Optional[str] = None,
    room: Optional[str] = None,
    conversation_session_id: Optional[str] = None,
    category: Optional[str] = None,
    limit: int = 5,
):
    """Public — CLOSED request history, retrieved ONLY on an explicit
    historical question ("what did I ask maintenance yesterday?", "when did
    they fix my light?"). Returns recently completed/skipped requests with
    their real lifecycle timestamps (completed_at etc). Never preloaded
    into a session; never unsolicited conversation material. History is
    preserved - records are never deleted."""
    q = _scope_query(resident_id, room, conversation_session_id)
    q["status"] = {"$in": CLOSED_TASK_STATUSES}
    if category:
        q["category"] = category
    tz = await _facility_tz()
    tasks = await db.staff_tasks.find(q, {"_id": 0}).sort(
        [("completed_at", -1), ("created_at", -1)],
    ).to_list(max(1, min(limit, 20)))
    return {"found": bool(tasks), "scope": "history",
            "requests": [_resident_safe_view(t, tz) for t in tasks]}


@router.get("/resident-request/mine")
async def resident_request_mine(resident_id: Optional[str] = None, room: Optional[str] = None, limit: int = 8):
    """Public — the resident Home screen's Requests panel. Same scoping
    discipline as /status (resident_id, else room - never a global 'latest
    requests' query) but returns several recent ones instead of just the
    newest, so a resident with more than one open request sees all of them
    as separate cards. Unlike /status this is not conversational context -
    it is the resident's own screen - so it still shows every recent
    request regardless of status, each with its real state/schedule."""
    q = _scope_query(resident_id, room, None, allow_session=False)
    tz = await _facility_tz()
    tasks = await db.staff_tasks.find(q, {"_id": 0}).sort("created_at", -1).to_list(max(1, min(limit, 30)))
    return [_resident_safe_view(t, tz) for t in tasks]
