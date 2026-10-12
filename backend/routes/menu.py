"""Menu lane - staff-entered items plus emailed/pasted menus
(menu_ingest.py), all behind one approval gate. Drafts are visible only
to staff; residents and Aria read published ("approved") items only.
Kitchen or Administration staff and admins may change the menu
(service_content_access.py).

The gate is the point: Aria must never read a draft item. A resident with
a dietary restriction or diabetes acting on a wrong "we're having X" is a
real health-adjacent failure, not just an annoyance.
"""
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends

from models import MenuItem, MenuItemCreate, MenuItemUpdate, now_utc
from deps import db, get_current_user
from routes.realtime_facility import today_facility_date
from routes.content_receipts import record_content_change, staff_actor, summarize
from routes.service_content_access import MENU_DEPARTMENTS, require_content_editor

router = APIRouter(prefix="/menu", tags=["menu"])


def _iso(doc: dict) -> dict:
    for k in ("created_at", "updated_at", "approved_at"):
        v = doc.get(k)
        if v and not isinstance(v, str):
            doc[k] = v.isoformat()
    return doc


@router.get("")
async def list_menu(date: Optional[str] = None, status: Optional[str] = None, user=Depends(get_current_user)):
    """Admin/staff view - every status, so staff can see what's still a draft."""
    q: dict = {"date": date or today_facility_date()}
    if status:
        q["status"] = status
    items = await db.menu_items.find(q, {"_id": 0}).sort("meal_period", 1).to_list(200)
    return [_iso(i) for i in items]


@router.post("")
async def create_menu_item(data: MenuItemCreate, user=Depends(get_current_user)):
    require_content_editor(user, MENU_DEPARTMENTS)
    item = MenuItem(**data.model_dump(), created_by=user["user_id"])
    doc = item.model_dump()
    doc["created_at"] = doc["created_at"].isoformat()
    doc["updated_at"] = doc["updated_at"].isoformat()
    await db.menu_items.insert_one(doc)
    doc.pop("_id", None)
    await record_content_change(kind="menu", action="created", object_type="menu_item", object_id=doc["menu_id"],
                                actor=staff_actor(user), after=summarize("menu", doc))
    return doc


async def _supersede(original_id: str, new_id: str, user: dict) -> None:
    """Retire the published item a correction replaces. Guarded: only a still
    published original can be superseded, so two competing corrections cannot
    both go live (409 for the second)."""
    before = await db.menu_items.find_one({"menu_id": original_id}, {"_id": 0})
    r = await db.menu_items.update_one(
        {"menu_id": original_id, "status": "approved"},
        {"$set": {"status": "superseded", "superseded_by": new_id, "updated_at": now_utc().isoformat()}})
    if r.modified_count == 0:
        raise HTTPException(status_code=409, detail="Another correction already replaced this item; edit the current item instead")
    await record_content_change(
        kind="menu", action="superseded", object_type="menu_item", object_id=original_id, actor=staff_actor(user),
        before=summarize("menu", before), after={"status": "superseded", "superseded_by": new_id},
        ingest_id=(before or {}).get("upload_id"))


async def _correct_published(existing: dict, fields: dict, publish: bool, user: dict) -> dict:
    """A correction of a published item is a new item that replaces it; the
    published one stays live (and unchanged) until the correction is published."""
    base = {k: existing.get(k) for k in ("date", "meal_period", "item_name", "description", "availability",
                                    "dietary_labels", "allergens", "upload_id")}
    item = MenuItem(**{**base, **fields}, source="staff_entry", replaces=existing["menu_id"], created_by=user["user_id"])
    doc = item.model_dump()
    now_iso = now_utc().isoformat()
    doc.update(created_at=now_iso, updated_at=now_iso)
    if publish:
        await _supersede(existing["menu_id"], doc["menu_id"], user)
        doc.update(status="approved", approved_by=user["user_id"], approved_at=now_iso)
    await db.menu_items.insert_one(doc)
    doc.pop("_id", None)
    await record_content_change(
        kind="menu", action="corrected", object_type="menu_item", object_id=doc["menu_id"], actor=staff_actor(user),
        before=summarize("menu", existing), after=summarize("menu", doc), ingest_id=doc.get("upload_id"),
        detail={"replaces": existing["menu_id"], "published": publish})
    return doc


@router.patch("/{menu_id}")
async def update_menu_item(menu_id: str, data: MenuItemUpdate, user=Depends(get_current_user)):
    """A correction. A published item is never overwritten: the correction is
    a new item that `replaces` it - a draft unless the editor publishes it in
    the same action (`publish: true`, editor = reviewer). The original stays
    live until the correction is published, then it is superseded (kept as
    history, labelled, not revivable). A draft is edited in place."""
    require_content_editor(user, MENU_DEPARTMENTS)
    existing = await db.menu_items.find_one({"menu_id": menu_id}, {"_id": 0})
    if not existing:
        raise HTTPException(status_code=404, detail="Menu item not found")
    if existing["status"] == "superseded":
        raise HTTPException(status_code=409, detail="This item was replaced by a newer menu; edit the current item instead")
    fields = data.model_dump(exclude_none=True)
    publish = fields.pop("publish", False)
    if existing["status"] == "approved":
        return _iso(await _correct_published(existing, fields, publish, user))
    if publish and existing.get("replaces"):
        await _supersede(existing["replaces"], menu_id, user)
    patch = dict(fields)
    now_iso = now_utc().isoformat()
    patch["updated_at"] = now_iso
    if publish:
        patch.update(status="approved", approved_by=user["user_id"], approved_at=now_iso)
    await db.menu_items.update_one({"menu_id": menu_id}, {"$set": patch})
    updated = await db.menu_items.find_one({"menu_id": menu_id}, {"_id": 0})
    await record_content_change(
        kind="menu", action="published" if publish else "edited", object_type="menu_item", object_id=menu_id,
        actor=staff_actor(user), before=summarize("menu", existing), after=summarize("menu", updated),
        ingest_id=updated.get("upload_id"))
    return _iso(updated)


@router.post("/{menu_id}/approve")
async def approve_menu_item(menu_id: str, user=Depends(get_current_user)):
    require_content_editor(user, MENU_DEPARTMENTS)
    existing = await db.menu_items.find_one({"menu_id": menu_id}, {"_id": 0})
    if not existing:
        raise HTTPException(status_code=404, detail="Menu item not found")
    if existing["status"] == "superseded":
        # Re-approving a replaced dish would put the old and the corrected
        # menu in front of residents side by side.
        raise HTTPException(status_code=409, detail="This item was replaced by a newer menu and cannot be published again")
    if existing["status"] == "draft" and existing.get("replaces"):
        await _supersede(existing["replaces"], menu_id, user)   # 409 if a competing correction already went live
    patch = {
        "status": "approved",
        "approved_by": user["user_id"],
        "approved_at": now_utc().isoformat(),
        "updated_at": now_utc().isoformat(),
    }
    await db.menu_items.update_one({"menu_id": menu_id}, {"$set": patch})
    updated = await db.menu_items.find_one({"menu_id": menu_id}, {"_id": 0})
    await record_content_change(
        kind="menu", action="published", object_type="menu_item", object_id=menu_id,
        actor=staff_actor(user), before=summarize("menu", existing), after=summarize("menu", updated),
        ingest_id=updated.get("upload_id"))
    return _iso(updated)


@router.delete("/{menu_id}")
async def delete_menu_item(menu_id: str, user=Depends(get_current_user)):
    require_content_editor(user, MENU_DEPARTMENTS)
    existing = await db.menu_items.find_one({"menu_id": menu_id}, {"_id": 0})
    r = await db.menu_items.delete_one({"menu_id": menu_id})
    if r.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Menu item not found")
    await record_content_change(kind="menu", action="deleted", object_type="menu_item", object_id=menu_id,
                                actor=staff_actor(user), before=summarize("menu", existing),
                                ingest_id=(existing or {}).get("upload_id"))
    return {"ok": True}


@router.get("/public/today")
async def public_today(date: Optional[str] = None, meal_period: Optional[str] = None):
    """No auth - same public trust model as the other resident-facing
    endpoints Aria calls live. HARD FILTER on status=approved - this is
    the actual enforcement point of the approval gate. An empty list is a
    real, honest answer ("no menu yet"), never an error, and never falls
    back to a draft."""
    q: dict = {"date": date or today_facility_date(), "status": "approved"}
    if meal_period:
        q["meal_period"] = meal_period
    items = await db.menu_items.find(q, {"_id": 0}).sort("meal_period", 1).to_list(200)
    return [
        {
            "meal_period": i["meal_period"],
            "item_name": i["item_name"],
            "description": i.get("description") or "",
            "availability": i.get("availability"),
            # staff-entered, repeated verbatim; an unlisted allergen is not a claim it is absent
            "dietary_labels": i.get("dietary_labels") or [],
            "allergens": i.get("allergens") or [],
        }
        for i in items
    ]
