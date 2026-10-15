"""Staff tasks — daily work assignment + completion log.

Workflow
  • Admin creates tasks (one-off) or templates (daily / per-shift recurring).
  • Admin triggers POST /api/tasks/spawn-today to materialize today's tasks from
    active templates (also run at seed-time + safe to re-run, idempotent on
    (template_id, due_date) pair).
  • Staff sees their queue, taps Start → status=in_progress + started_at,
    taps Complete → status=completed + completed_at + duration_minutes + notes.
  • Full audit trail: who did what, when, how long, what notes.
"""
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends
from models import StaffTask, StaffTaskCreate, StaffTaskUpdate
from deps import db
from routes import task_actions, task_lifecycle, task_ride_link, task_work_rules
from routes.actor_context import actor_from_user
from routes.task_lifecycle import record_origin, simulation_marker, work_as_authority
from routes.work_context import get_department_user

router = APIRouter(prefix="/tasks", tags=["tasks"])


def _iso(doc: dict) -> dict:
    for k in ("created_at", "started_at", "completed_at", "due_at"):
        v = doc.get(k)
        if v and not isinstance(v, str):
            doc[k] = v.isoformat()
    return doc


async def _resolve_denorms(data: dict) -> dict:
    """Fill assigned_name, resident_name, room from foreign keys."""
    if data.get("assigned_to"):
        u = await db.users.find_one({"user_id": data["assigned_to"]}, {"_id": 0, "name": 1})
        if u:
            data["assigned_name"] = u.get("name")
    if data.get("resident_id"):
        r = await db.residents.find_one({"resident_id": data["resident_id"]}, {"_id": 0, "name": 1, "room": 1})
        if r:
            data["resident_name"] = r.get("name")
            if not data.get("room"):
                data["room"] = r.get("room")
    return data


def staff_visibility_query(user) -> dict:
    """The one definition of which tasks a user may see in a list: a staff user sees their department's requests
    plus all_staff ones (no department: only all_staff); owner, admin and front desk see everything unless they
    explicitly entered a department Work-as context. Used by the task list and task detail so they cannot drift."""
    if user.get("role") != "staff" and not user.get("_work_context_id"):
        return {}
    dept = user.get("department")
    return {"visibility_role": {"$in": [dept, "all_staff"]} if dept else "all_staff"}


# ================= TASKS =================
@router.get("")
async def list_tasks(
    mine_only: bool = False,
    status: Optional[str] = None,
    day: Optional[str] = None,  # YYYY-MM-DD filter
    category: Optional[str] = None,
    visibility_role: Optional[str] = None,
    resident_id: Optional[str] = None,
    view: Optional[str] = None,   # current | review (operations_currency); default: everything
    user=Depends(get_department_user),
):
    q: dict = {}
    if resident_id:
        q["resident_id"] = resident_id
    if mine_only:
        q["assigned_to"] = user["user_id"]
        if user.get("_work_context_id"):
            q.update(staff_visibility_query(user))
    else:
        q.update(staff_visibility_query(user))
    if status:
        q["status"] = status
    if category:
        q["category"] = category
    if visibility_role and user.get("role") != "staff":
        q["visibility_role"] = visibility_role
    if day:
        start = f"{day}T00:00:00+00:00"
        end = f"{day}T23:59:59+00:00"
        q["created_at"] = {"$gte": start, "$lte": end}

    items = await db.staff_tasks.find(q, {"_id": 0}).sort("created_at", -1).to_list(500)
    for t in items:
        _iso(t)
    from routes.operations_currency import annotate, filter_view   # lazy: avoids a module cycle
    return filter_view(await annotate(items, "task"), view)


@router.post("")
async def create_task(data: StaffTaskCreate, user=Depends(get_department_user)):
    role = user.get("role")
    if role in ("owner", "admin"):
        authority = f"admin_override:{role}"
    else:
        # A department member (staff WITH a department) may open work only
        # for their OWN department - visibility_role and category are forced
        # to their department slug so a department workspace can never
        # create cross-department work. Everyone else is rejected. This is
        # what lets a Maintenance lead raise a work order without an admin.
        dept = user.get("department")
        if role == "staff" and dept:
            data.visibility_role = dept
            data.category = dept
            authority = work_as_authority(user, f"dept_member:{dept}")
        else:
            raise HTTPException(status_code=403, detail="Not allowed to create work here")
    payload = data.model_dump()
    await _resolve_denorms(payload)
    payload.update(await simulation_marker(payload.get("resident_id")))
    task = StaffTask(**payload)
    doc = task.model_dump()
    doc["created_at"] = doc["created_at"].isoformat()
    if doc.get("due_at") and not isinstance(doc["due_at"], str):
        doc["due_at"] = doc["due_at"].isoformat()
    await db.staff_tasks.insert_one(doc)
    doc.pop("_id", None)
    await record_origin(doc, actor_from_user(user), action_type="task_created", authority=authority)
    return doc


@router.patch("/{task_id}")
async def update_task(task_id: str, data: StaffTaskUpdate, user=Depends(get_department_user)):
    """A note and/or the planned service window. Status and assignment are
    not settable here (StaffTaskUpdate forbids them): they go through the
    lifecycle endpoints, which authorize and receipt each step."""
    actor = actor_from_user(user)
    patch = data.model_dump(exclude_unset=True)
    notes = patch.pop("notes", None) if "notes" in patch else None
    has_notes = "notes" in data.model_fields_set
    details = {k: patch.pop(k) for k in list(patch) if k in task_actions.DETAIL_FIELDS}
    override = bool(patch.pop("conflict_override", False))
    conflicts = []
    if patch or "provider_name" in details:
        # A new window, or a new provider on planned work, is checked for overlap with the
        # resident's other planned work and with the same provider / assignee's work for
        # other residents. Refused (409, nothing written) unless staff save anyway; the
        # override is recorded on the receipt. Authority first (403 / 409 closed / legacy
        # refusal), so a caller who may not plan this request never learns what else is planned.
        from routes import schedule_conflict   # lazy: it reads request modules that import this route
        current, _auth, _head = await task_lifecycle.check(task_id, actor, user,
                                                           action="schedule" if patch else "details")
        prospective = {**current, **{k: ((v or "").strip() or None) for k, v in details.items()}}
        window = {k: patch.get(k, current.get(k)) for k in ("requested_for_date", "requested_for_time_label")}
        if window["requested_for_date"]:
            chk = await schedule_conflict.find_conflicts(prospective, window["requested_for_date"],
                                                         window["requested_for_time_label"])
            if chk["conflicts"] and not override:
                raise HTTPException(status_code=409, detail={"code": "schedule_conflict",
                                    "message": "This window overlaps other planned work (this resident's, or the same "
                                               "provider or staff member's). Save anyway to keep it.",
                                    **chk})
            conflicts = chk["conflicts"] if override else []
    if has_notes:
        await task_actions.add_note(task_id, notes, actor, user)
    if details:
        await task_actions.set_details(task_id, details, actor, user,
                                       override_conflicts=conflicts if (conflicts and not patch) else None)
    if patch:
        task, receipt = await task_actions.set_schedule(task_id, patch, actor, user,
                                                        override_conflicts=conflicts or None)
        if receipt:   # the window really changed: a linked open ride follows it
            await task_ride_link.sync_schedule(task, user)
    return _iso(await task_lifecycle.load(task_id))


@router.post("/{task_id}/acknowledge")
async def acknowledge_task(task_id: str, user=Depends(get_department_user)):
    """Distinct from /start - 'someone has seen this' vs 'work has begun'."""
    task, _ = await task_actions.acknowledge(task_id, actor_from_user(user), user)
    return _iso(task)


@router.post("/{task_id}/start")
async def start_task(task_id: str, user=Depends(get_department_user)):
    task, _ = await task_actions.start(task_id, actor_from_user(user), user)
    return _iso(task)


@router.post("/{task_id}/complete")
async def complete_task(task_id: str, body: dict = None, user=Depends(get_department_user)):
    body = body or {}
    task, _ = await task_actions.complete(task_id, body.get("notes"), actor_from_user(user), user,
                                          override_reason=body.get("override_reason"))
    return _iso(task)


@router.post("/{task_id}/skip")
async def skip_task(task_id: str, body: dict = None, user=Depends(get_department_user)):
    await task_work_rules.check_cancel(task_id, (body or {}).get("notes"), actor_from_user(user), user)
    task, _ = await task_actions.skip(task_id, (body or {}).get("notes"), actor_from_user(user), user)
    await task_ride_link.cancel_linked(task, user, (body or {}).get("notes"))   # a linked open ride is cancelled too
    return _iso(task)


@router.post("/{task_id}/ride")
async def request_ride_for_task(task_id: str, user=Depends(get_department_user)):
    """Create-or-attach exactly one transportation request for a planned request."""
    return await task_ride_link.request_ride(task_id, actor_from_user(user), user)


@router.get("/{task_id}/ride")
async def ride_for_task(task_id: str, user=Depends(get_department_user)):
    return await task_ride_link.get_ride(task_id, actor_from_user(user), user)


@router.post("/{task_id}/reopen")
async def reopen_task(task_id: str, body: dict = None, user=Depends(get_department_user)):
    """Reopen a completed/skipped request with a stated reason (receipted)."""
    task, _ = await task_actions.reopen(task_id, (body or {}).get("reason"), actor_from_user(user), user)
    return _iso(task)


@router.delete("/{task_id}")
async def delete_task(task_id: str, user=Depends(get_department_user)):
    await task_actions.delete(task_id, actor_from_user(user), user)
    return {"ok": True}
