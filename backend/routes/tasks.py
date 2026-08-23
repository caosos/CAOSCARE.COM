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
from models import StaffTask, StaffTaskCreate, StaffTaskUpdate, now_utc
from deps import db, get_current_user
from routes.receipts import create_receipt, update_receipt_status

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


async def _notify_department(visibility_role: str, subject: str, body: str) -> None:
    """Email everyone in the target department. Reuses the existing staff
    account directory (User.email) as the one source of truth for who's in
    a department, instead of inventing a separate department-contacts list
    Michael would have to type in by hand. If nobody has that department
    set yet (true for a brand-new facility), falls back to admin/owner so
    a request is never silently un-notified. send_email() itself already
    degrades gracefully to a logged-only record when no provider key is
    configured - this never blocks the caller."""
    recipients = await db.users.find(
        {"department": visibility_role}, {"_id": 0, "email": 1}
    ).to_list(50)
    if not recipients:
        recipients = await db.users.find(
            {"role": {"$in": ["admin", "owner"]}}, {"_id": 0, "email": 1}
        ).to_list(50)
    for u in recipients:
        if u.get("email"):
            await send_email(u["email"], subject, body)


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


@router.post("/{task_id}/acknowledge")
async def acknowledge_task(task_id: str, user=Depends(get_current_user)):
    """Distinct from /start - 'someone has seen this' vs 'work has begun'.
    Real event Michael's Communication & Requests timeline needs (previously
    unwired: acknowledged_by/acknowledged_at existed on StaffTask but nothing
    ever set them)."""
    existing = await db.staff_tasks.find_one({"task_id": task_id}, {"_id": 0})
    if not existing:
        raise HTTPException(status_code=404, detail="Task not found")
    if not existing.get("acknowledged_at"):
        await db.staff_tasks.update_one(
            {"task_id": task_id},
            {"$set": {
                "acknowledged_by": user["user_id"], "acknowledged_by_name": user.get("name"),
                "acknowledged_at": now_utc().isoformat(),
            }},
        )
        await update_receipt_status("task", task_id, "acknowledged")
    return _iso(await db.staff_tasks.find_one({"task_id": task_id}, {"_id": 0}))


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

