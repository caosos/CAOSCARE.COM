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
from deps import db, get_current_user
from routes import task_actions, task_lifecycle
from routes.actor_context import actor_from_user
from routes.task_lifecycle import record_origin, simulation_marker

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


# ================= TASKS =================
@router.get("")
async def list_tasks(
    mine_only: bool = False,
    status: Optional[str] = None,
    day: Optional[str] = None,  # YYYY-MM-DD filter
    category: Optional[str] = None,
    visibility_role: Optional[str] = None,
    resident_id: Optional[str] = None,
    user=Depends(get_current_user),
):
    q: dict = {}
    if resident_id:
        q["resident_id"] = resident_id
    if mine_only:
        q["assigned_to"] = user["user_id"]
    elif user.get("role") == "staff":
        # Department-scoped visibility (item 4, Terminal 8): a staff user
        # with a department sees that department's requests plus general
        # ones; a staff user with no department sees only general/
        # all_staff-visibility items. Admin/owner see everything, per
        # "admin/owner visibility remains appropriately broad."
        dept = user.get("department")
        q["visibility_role"] = {"$in": [dept, "all_staff"]} if dept else "all_staff"
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
    return items


@router.post("")
async def create_task(data: StaffTaskCreate, user=Depends(get_current_user)):
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
            authority = f"dept_member:{dept}"
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
async def update_task(task_id: str, data: StaffTaskUpdate, user=Depends(get_current_user)):
    """A note and/or the planned service window. Status and assignment are
    not settable here (StaffTaskUpdate forbids them): they go through the
    lifecycle endpoints, which authorize and receipt each step."""
    actor = actor_from_user(user)
    patch = data.model_dump(exclude_unset=True)
    if "notes" in patch:
        await task_actions.add_note(task_id, patch.pop("notes"), actor, user)
    if patch:
        await task_actions.set_schedule(task_id, patch, actor, user)
    return _iso(await task_lifecycle.load(task_id))


@router.post("/{task_id}/acknowledge")
async def acknowledge_task(task_id: str, user=Depends(get_current_user)):
    """Distinct from /start - 'someone has seen this' vs 'work has begun'."""
    task, _ = await task_actions.acknowledge(task_id, actor_from_user(user), user)
    return _iso(task)


@router.post("/{task_id}/start")
async def start_task(task_id: str, user=Depends(get_current_user)):
    task, _ = await task_actions.start(task_id, actor_from_user(user), user)
    return _iso(task)


@router.post("/{task_id}/complete")
async def complete_task(task_id: str, body: dict = None, user=Depends(get_current_user)):
    task, _ = await task_actions.complete(task_id, (body or {}).get("notes"), actor_from_user(user), user)
    return _iso(task)


@router.post("/{task_id}/skip")
async def skip_task(task_id: str, body: dict = None, user=Depends(get_current_user)):
    task, _ = await task_actions.skip(task_id, (body or {}).get("notes"), actor_from_user(user), user)
    return _iso(task)


@router.delete("/{task_id}")
async def delete_task(task_id: str, user=Depends(get_current_user)):
    await task_actions.delete(task_id, actor_from_user(user), user)
    return {"ok": True}
