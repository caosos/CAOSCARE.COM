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
from models import (
    StaffTask, StaffTaskCreate, StaffTaskUpdate,
    StaffTaskTemplate, StaffTaskTemplateCreate,
    now_utc,
)
from deps import db, get_current_user

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
    user=Depends(get_current_user),
):
    q: dict = {}
    if mine_only or user.get("role") == "staff":
        q["assigned_to"] = user["user_id"]
    if status:
        q["status"] = status
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
    return doc


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
