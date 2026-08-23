"""Admin-managed department list - replaces the old fixed StaffDepartment
Literal. One source of truth for "who can a request route to": staff pick
their department from this list, resident-request categories validate
against it, and Aria's tool schemas build their enum from it at
session-mint time (see get_active_departments(), imported by
realtime_tools_operations.py and resident_requests.py).

Two department slugs are seeded and treated as special by convention
elsewhere in the app, not enforced here: "administration" (the fallback
notify_department() and the resident-request bus use when a category has
no matching department) and any department a StaffTask's visibility_role
already points at from before this model existed.
"""
import re
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends

from models import Department, DepartmentCreate, DepartmentUpdate, now_utc
from deps import db, require_admin

router = APIRouter(prefix="/departments", tags=["departments"])

DEFAULT_DEPARTMENTS = ["Nursing", "Maintenance", "Kitchen", "Housekeeping", "Administration", "Transportation"]


def _slugify(label: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "_", label.strip().lower()).strip("_")
    return s or "department"


async def seed_default_departments() -> None:
    """Idempotent - called once at server startup. Only inserts if the
    collection is empty, so it never overwrites anything Michael has
    already edited (renamed, deactivated, etc.)."""
    if await db.departments.count_documents({}) > 0:
        return
    for label in DEFAULT_DEPARTMENTS:
        dept = Department(slug=_slugify(label), label=label)
        doc = dept.model_dump()
        doc["created_at"] = doc["created_at"].isoformat()
        await db.departments.insert_one(doc)


async def get_active_departments() -> list[dict]:
    """Importable helper - the live {slug, label} list other modules build
    their department-facing UI/tool options from. Only active departments,
    since a deactivated one shouldn't be offered as a new routing target
    (existing records that already point at it are untouched)."""
    items = await db.departments.find({"active": True}, {"_id": 0, "slug": 1, "label": 1}).sort("label", 1).to_list(100)
    return items


@router.get("")
async def list_departments(user=Depends(require_admin)):
    items = await db.departments.find({}, {"_id": 0}).sort("label", 1).to_list(100)
    for i in items:
        if not isinstance(i.get("created_at"), str):
            i["created_at"] = i["created_at"].isoformat()
    return items


@router.post("")
async def create_department(data: DepartmentCreate, user=Depends(require_admin)):
    slug = _slugify(data.label)
    if await db.departments.find_one({"slug": slug}):
        raise HTTPException(status_code=400, detail=f"A department matching '{data.label}' already exists")
    dept = Department(slug=slug, label=data.label, description=data.description, contact_email=data.contact_email)
    doc = dept.model_dump()
    doc["created_at"] = doc["created_at"].isoformat()
    await db.departments.insert_one(doc)
    doc.pop("_id", None)
    return doc


@router.patch("/{department_id}")
async def update_department(department_id: str, data: DepartmentUpdate, user=Depends(require_admin)):
    """slug is intentionally never editable - it's what every existing
    User.department/StaffTask.visibility_role reference is stable against.
    Only the display label/description/contact/active state can change."""
    existing = await db.departments.find_one({"department_id": department_id}, {"_id": 0})
    if not existing:
        raise HTTPException(status_code=404, detail="Department not found")
    patch = {k: v for k, v in data.model_dump(exclude_none=True).items()}
    if patch:
        await db.departments.update_one({"department_id": department_id}, {"$set": patch})
    return await db.departments.find_one({"department_id": department_id}, {"_id": 0})


@router.delete("/{department_id}")
async def delete_department(department_id: str, user=Depends(require_admin)):
    r = await db.departments.delete_one({"department_id": department_id})
    if r.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Department not found")
    return {"ok": True}
