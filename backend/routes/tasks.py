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
from datetime import datetime, timezone, timedelta
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from models import (
    StaffTask, StaffTaskCreate, StaffTaskUpdate,
    StaffTaskTemplate, StaffTaskTemplateCreate,
    TaskCategory, TaskPriority, now_utc,
)
from deps import db, get_current_user
from routes.receipts import create_receipt, update_receipt_status

router = APIRouter(prefix="/tasks", tags=["tasks"])

# Categories a resident/Aria may raise directly (item 3/4/5, Terminal 8).
# Deliberately narrower than the full staff TaskCategory list - a resident
# request should never be able to create e.g. a "paperwork" task, and the
# visibility_role is derived from category, not caller-supplied, so a
# resident-originated request can't be routed to see other roles' queues.
RESIDENT_REQUEST_CATEGORIES: dict[str, str] = {
    "nursing": "nursing",
    "maintenance": "maintenance",
    "kitchen": "kitchen",
    "front_desk": "administration",
    "complaint": "administration",
    "housekeeping": "housekeeping",
}


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
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin required")
    payload = data.model_dump()
    await _resolve_denorms(payload)
    task = StaffTask(**payload)
    doc = task.model_dump()
    doc["created_at"] = doc["created_at"].isoformat()
    if doc.get("due_at") and not isinstance(doc["due_at"], str):
        doc["due_at"] = doc["due_at"].isoformat()
    await db.staff_tasks.insert_one(doc)
    doc.pop("_id", None)
    await create_receipt(
        action_type="task_created", related_object_type="task", related_object_id=doc["task_id"],
        source="staff", resident_id=doc.get("resident_id"), room=doc.get("room"),
        requested_by=user["user_id"], assigned_role=doc.get("visibility_role"),
        assigned_user=doc.get("assigned_to"),
    )
    return doc


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
    truthfully: created, not "someone is on the way"."""
    visibility_role = RESIDENT_REQUEST_CATEGORIES.get(data.category)
    if not visibility_role:
        raise HTTPException(status_code=400, detail=f"Unsupported request category: {data.category}")
    if data.source not in ("aria_voice", "kiosk_button"):
        raise HTTPException(status_code=400, detail="Invalid source")

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
    return {"task_id": doc["task_id"], "receipt_id": receipt["receipt_id"], "status": doc["status"]}


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
    browse other residents'/sessions' requests. resident_id was previously
    a required param with no default, which would 422 before this logic
    ever ran - fixed alongside adding the session-scoped fallback."""
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
    return {
        "found": True,
        "category": task["category"],
        "status": task["status"],
        "acknowledged": bool(task.get("acknowledged_at") or task["status"] in ("in_progress", "completed")),
        "assigned_to_name": task.get("assigned_name"),
        "created_at": task["created_at"] if isinstance(task["created_at"], str) else task["created_at"].isoformat(),
    }


@router.patch("/{task_id}")
async def update_task(task_id: str, data: StaffTaskUpdate, user=Depends(get_current_user)):
    existing = await db.staff_tasks.find_one({"task_id": task_id}, {"_id": 0})
    if not existing:
        raise HTTPException(status_code=404, detail="Task not found")
    if user.get("role") != "admin" and existing.get("assigned_to") != user["user_id"]:
        raise HTTPException(status_code=403, detail="Not your task")

    patch = {k: v for k, v in data.model_dump(exclude_none=True).items()}
    if "assigned_to" in patch:
        await _resolve_denorms(patch)
    await db.staff_tasks.update_one({"task_id": task_id}, {"$set": patch})
    updated = await db.staff_tasks.find_one({"task_id": task_id}, {"_id": 0})
    return _iso(updated)


@router.post("/{task_id}/start")
async def start_task(task_id: str, user=Depends(get_current_user)):
    existing = await db.staff_tasks.find_one({"task_id": task_id}, {"_id": 0})
    if not existing:
        raise HTTPException(status_code=404, detail="Task not found")
    patch = {
        "status": "in_progress",
        "started_at": now_utc().isoformat(),
        "assigned_to": existing.get("assigned_to") or user["user_id"],
        "assigned_name": existing.get("assigned_name") or user.get("name"),
    }
    await db.staff_tasks.update_one({"task_id": task_id}, {"$set": patch})
    await update_receipt_status("task", task_id, "in_progress")
    return _iso(await db.staff_tasks.find_one({"task_id": task_id}, {"_id": 0}))


@router.post("/{task_id}/complete")
async def complete_task(task_id: str, body: dict = None, user=Depends(get_current_user)):
    existing = await db.staff_tasks.find_one({"task_id": task_id}, {"_id": 0})
    if not existing:
        raise HTTPException(status_code=404, detail="Task not found")
    body = body or {}
    started = existing.get("started_at")
    duration = None
    finished = now_utc()
    if started:
        try:
            started_dt = datetime.fromisoformat(started.replace("Z", "+00:00"))
            duration = round((finished - started_dt).total_seconds() / 60.0, 1)
        except Exception:
            pass
    patch = {
        "status": "completed",
        "completed_at": finished.isoformat(),
        "completed_by": user["user_id"],
        "completed_by_name": user.get("name"),
        "duration_minutes": duration,
        "notes": body.get("notes") or existing.get("notes") or "",
    }
    if not existing.get("started_at"):
        patch["started_at"] = finished.isoformat()
    await db.staff_tasks.update_one({"task_id": task_id}, {"$set": patch})
    await update_receipt_status("task", task_id, "completed", result=patch["notes"] or "completed")
    return _iso(await db.staff_tasks.find_one({"task_id": task_id}, {"_id": 0}))


@router.post("/{task_id}/skip")
async def skip_task(task_id: str, body: dict = None, user=Depends(get_current_user)):
    body = body or {}
    existing = await db.staff_tasks.find_one({"task_id": task_id}, {"_id": 0})
    if not existing:
        raise HTTPException(status_code=404, detail="Task not found")
    patch = {
        "status": "skipped",
        "completed_at": now_utc().isoformat(),
        "completed_by": user["user_id"],
        "completed_by_name": user.get("name"),
        "notes": body.get("notes") or existing.get("notes") or "",
    }
    await db.staff_tasks.update_one({"task_id": task_id}, {"$set": patch})
    await update_receipt_status("task", task_id, "cancelled", failure_reason=patch["notes"] or "skipped")
    return _iso(await db.staff_tasks.find_one({"task_id": task_id}, {"_id": 0}))


@router.delete("/{task_id}")
async def delete_task(task_id: str, user=Depends(get_current_user)):
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin required")
    r = await db.staff_tasks.delete_one({"task_id": task_id})
    if r.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"ok": True}


# ================= TEMPLATES =================
@router.get("/templates/all")
async def list_templates(user=Depends(get_current_user)):
    items = await db.task_templates.find({}, {"_id": 0}).sort("title", 1).to_list(500)
    for t in items:
        _iso(t)
    return items


@router.post("/templates")
async def create_template(data: StaffTaskTemplateCreate, user=Depends(get_current_user)):
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin required")
    tpl = StaffTaskTemplate(**data.model_dump())
    doc = tpl.model_dump()
    doc["created_at"] = doc["created_at"].isoformat()
    await db.task_templates.insert_one(doc)
    doc.pop("_id", None)
    return doc


@router.delete("/templates/{template_id}")
async def delete_template(template_id: str, user=Depends(get_current_user)):
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin required")
    r = await db.task_templates.delete_one({"template_id": template_id})
    if r.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Template not found")
    return {"ok": True}


@router.post("/spawn-today")
async def spawn_today(user=Depends(get_current_user)):
    """Idempotent — materializes one task per active template for today's date."""
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin required")
    today = now_utc().date().isoformat()
    start = f"{today}T00:00:00+00:00"
    end = f"{today}T23:59:59+00:00"
    created = 0
    async for tpl in db.task_templates.find({"active": True}, {"_id": 0}):
        # Skip if a task from this template already exists today
        existing = await db.staff_tasks.find_one({
            "template_id": tpl["template_id"],
            "created_at": {"$gte": start, "$lte": end},
        }, {"_id": 0})
        if existing:
            continue
        payload = {
            "title": tpl["title"],
            "description": tpl.get("description", ""),
            "category": tpl.get("category", "other"),
            "shift": tpl.get("shift", "any"),
            "resident_id": tpl.get("resident_id"),
            "room": tpl.get("room"),
            "template_id": tpl["template_id"],
        }
        await _resolve_denorms(payload)
        task = StaffTask(**payload)
        doc = task.model_dump()
        doc["created_at"] = doc["created_at"].isoformat()
        await db.staff_tasks.insert_one(doc)
        created += 1
    return {"ok": True, "created": created, "date": today}
