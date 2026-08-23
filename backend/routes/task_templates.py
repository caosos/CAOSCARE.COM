"""Recurring staff-task templates + daily spawn - split out of tasks.py to
keep both under the 300-line cap. Distinct responsibility from individual
task lifecycle: this manages the recurring definitions; tasks.py owns the
actual per-day StaffTask records they spawn.
"""
from fastapi import APIRouter, HTTPException, Depends

from models import StaffTask, StaffTaskTemplate, StaffTaskTemplateCreate, now_utc
from deps import db, get_current_user
from routes.tasks import _iso, _resolve_denorms

router = APIRouter(prefix="/tasks", tags=["task-templates"])


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
