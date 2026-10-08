"""Menu email ingestion - the adapter boundary described in the Terminal 8
handoff: email is source/provenance/transport, never the domain model.

Two triggers now share the exact same internal ingestion function
(create_menu_upload() below): the dev-test endpoint (auth'd staff, still
useful for acceptance testing without waiting on a real inbound email) and
the real inbound-email webhook (backend/routes/email_inbound.py, which
receives at menu@inbound.caoscare.com via Resend and calls create_menu_upload()
directly - a Python function call, not a second HTTP round trip). There is
deliberately no separate parsing/creation logic for either path.

Parser is deliberately simple and honest: plain-text body only, looks for
"Breakfast"/"Lunch"/"Dinner or Supper" section headers and comma/line-
separated items underneath each. No PDF/image/attachment support (out of
scope per the directive - "do not turn attachment support into a giant
document-processing project"). Anything it can't confidently find is
flagged needs_review rather than guessed.
"""
import re
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends

from models import MenuItem, MenuUpload, now_utc
from deps import db, get_current_user
from routes.actor_context import ActorContext
from routes.content_receipts import inbound_email_actor, record_content_change, staff_actor
from routes.service_content_access import MENU_DEPARTMENTS, require_content_editor

router = APIRouter(prefix="/menu", tags=["menu"])

_SECTION_RE = re.compile(
    r"(breakfast|lunch|dinner|supper)\s*:?\s*\n?(.*?)(?=\n\s*(?:breakfast|lunch|dinner|supper)\s*:|\Z)",
    re.IGNORECASE | re.DOTALL,
)
_VEG_RE = re.compile(r"\bvegetarian\s*:", re.IGNORECASE)
_MEAL_ALIASES = {"breakfast": "breakfast", "lunch": "lunch", "dinner": "dinner", "supper": "dinner"}


def _parse_menu_email(raw_text: str) -> tuple[list[dict], str, Optional[str]]:
    """Returns (items, parse_status, parse_notes). Each item is
    {meal_period, item_name}. Deterministic, no model call - see module
    docstring for why that's the right call for this dev-test path."""
    items = []
    found_meals = set()
    for m in _SECTION_RE.finditer(raw_text):
        meal = _MEAL_ALIASES[m.group(1).lower()]
        found_meals.add(meal)
        body = m.group(2).strip()
        # Split on newlines or commas, drop empties/whitespace-only lines.
        # A mid-line "Vegetarian:" also separates; the dish after it is tagged
        # in `description` (MenuItem has no dedicated tag field).
        for raw_line in re.split(r"[\n,]", body):
            for k, part in enumerate(_VEG_RE.split(raw_line)):
                name = part.strip(" \t-*•").strip().rstrip(".").strip()
                if name:
                    it = {"meal_period": meal, "item_name": name}
                    if k:
                        it["description"] = "Vegetarian"
                    items.append(it)
    if not found_meals:
        return [], "needs_review", "Could not find Breakfast/Lunch/Dinner section headers in the email body."
    # Only warn about meals the text mentions but no section could be read.
    missing = {m for m in {"breakfast", "lunch", "dinner"} - found_meals
               if re.search(rf"\b{m}\b", raw_text, re.IGNORECASE)}
    if missing:
        return items, "needs_review", f"No section found for: {', '.join(sorted(missing))}."
    return items, "parsed", None


async def create_menu_upload(
    *, raw_text: str, service_date: str, source: str,
    source_ref: Optional[str] = None, created_by: Optional[str] = None,
    actor: Optional[ActorContext] = None,
) -> dict:
    """The one internal ingestion function for a menu email, real or
    dev-test - parses raw_text, creates the MenuUpload + its draft
    MenuItem rows, and returns the upload doc. `source` is provenance
    only ("email_dev_test" | "email" | anything else a future caller
    supplies) - the parsing/creation logic never branches on it.
    Items stay draft/needs_review until a staff member approves the
    upload via POST /menu/uploads/{id}/approve - a real inbound email
    can never publish directly to the public menu on its own.

    Writes one receipt for the batch. `actor` is the signed-in user's
    context; without one (the inbound-email process) the receipt names that
    process."""
    parsed_items, parse_status, parse_notes = _parse_menu_email(raw_text)

    upload = MenuUpload(
        source=source,
        source_ref=source_ref,
        raw_text=raw_text,
        service_date=service_date,
        parse_status=parse_status,
        parse_notes=parse_notes,
        created_by=created_by,
    )
    upload_doc = upload.model_dump()
    upload_doc["created_at"] = upload_doc["created_at"].isoformat()

    item_ids = []
    for it in parsed_items:
        mi = MenuItem(
            date=service_date, meal_period=it["meal_period"], item_name=it["item_name"],
            description=it.get("description", ""),
            source=source, upload_id=upload_doc["upload_id"],
        )
        mi_doc = mi.model_dump()
        mi_doc["created_at"] = mi_doc["created_at"].isoformat()
        mi_doc["updated_at"] = mi_doc["updated_at"].isoformat()
        await db.menu_items.insert_one(mi_doc)
        item_ids.append(mi_doc["menu_id"])

    upload_doc["item_ids"] = item_ids
    await db.menu_uploads.insert_one(dict(upload_doc))
    upload_doc.pop("_id", None)
    await record_content_change(
        kind="menu", action="uploaded", object_type="menu_upload", object_id=upload_doc["upload_id"],
        actor=actor or inbound_email_actor(), ingest_id=upload_doc["upload_id"],
        after={"status": upload_doc.get("status"), "service_date": service_date, "source": source,
               "item_count": len(item_ids), "parse_status": parse_status})
    return upload_doc


@router.post("/ingest/dev-test")
async def ingest_dev_test(body: dict, user=Depends(get_current_user)):
    """Simulates 'an email arrived' for development/acceptance testing,
    without needing a real inbound email. Body: {service_date, raw_text,
    source_ref?}. service_date is required explicitly rather than guessed
    from free text - real date-detection from an arbitrary email body is
    exactly the kind of fragile guessing this project avoids. The real
    inbound-email webhook (email_inbound.py) determines service_date
    itself (an explicit "Date: YYYY-MM-DD" line in the body, falling back
    to the facility's own today) before calling the same
    create_menu_upload() this endpoint calls."""
    require_content_editor(user, MENU_DEPARTMENTS)
    service_date = body.get("service_date")
    raw_text = (body.get("raw_text") or "")[:8000]
    if not service_date or not raw_text.strip():
        raise HTTPException(status_code=400, detail="service_date and raw_text are required")

    return await create_menu_upload(
        raw_text=raw_text, service_date=service_date, source="email_dev_test",
        source_ref=body.get("source_ref"), created_by=user["user_id"], actor=staff_actor(user),
    )


@router.post("/ingest/paste")
async def ingest_paste(body: dict, user=Depends(get_current_user)):
    """Kitchen staff paste the day's menu text (the menu screen's "Paste a
    menu"). Same parser and draft batch as an emailed menu - only the
    provenance differs (source="staff_paste"). Body: {service_date, raw_text}."""
    require_content_editor(user, MENU_DEPARTMENTS)
    service_date = body.get("service_date")
    raw_text = (body.get("raw_text") or "")[:8000]
    if not service_date or not raw_text.strip():
        raise HTTPException(status_code=400, detail="service_date and raw_text are required")
    return await create_menu_upload(
        raw_text=raw_text, service_date=service_date, source="staff_paste", created_by=user["user_id"],
        actor=staff_actor(user),
    )


@router.get("/uploads")
async def list_uploads(service_date: Optional[str] = None, user=Depends(get_current_user)):
    if user.get("role") not in ("admin", "owner", "staff"):
        raise HTTPException(status_code=403, detail="Staff required")
    q: dict = {}
    if service_date:
        q["service_date"] = service_date
    items = await db.menu_uploads.find(q, {"_id": 0}).sort("created_at", -1).to_list(100)
    for i in items:
        for k in ("created_at", "approved_at"):
            v = i.get(k)
            if v and not isinstance(v, str):
                i[k] = v.isoformat()
    return items


@router.post("/uploads/{upload_id}/approve")
async def approve_upload(upload_id: str, user=Depends(get_current_user)):
    """Approves the upload AND every MenuItem it produced in one action -
    the batch-level convenience the staff-view requirement asks for.

    Daily-replacement rule: if an earlier upload already has approved items
    for the same (date, meal_period), this new upload supersedes them
    (status -> "superseded", excluded from Aria's public read, but kept in
    the database for history/provenance) rather than showing both the old
    and corrected menu side by side. Scoped to whole-upload batches only -
    a single manual edit via /menu/{menu_id}/approve does NOT trigger this,
    since that's fixing one dish, not replacing the day's whole meal."""
    require_content_editor(user, MENU_DEPARTMENTS)
    upload = await db.menu_uploads.find_one({"upload_id": upload_id}, {"_id": 0})
    if not upload:
        raise HTTPException(status_code=404, detail="Upload not found")
    now_iso = now_utc().isoformat()
    meal_periods = set(
        i["meal_period"] for i in await db.menu_items.find(
            {"menu_id": {"$in": upload.get("item_ids", [])}}, {"_id": 0, "meal_period": 1}
        ).to_list(200)
    )
    superseded_ids: list = []
    if meal_periods:
        replace_q = {
            "date": upload["service_date"],
            "meal_period": {"$in": list(meal_periods)},
            "status": "approved",
            "menu_id": {"$nin": upload.get("item_ids", [])},
        }
        superseded_ids = [i["menu_id"] for i in await db.menu_items.find(replace_q, {"_id": 0, "menu_id": 1}).to_list(200)]
        await db.menu_items.update_many(replace_q, {"$set": {"status": "superseded", "updated_at": now_iso}})

    await db.menu_uploads.update_one(
        {"upload_id": upload_id},
        {"$set": {"status": "approved", "approved_by": user["user_id"], "approved_at": now_iso}},
    )
    await db.menu_items.update_many(
        {"menu_id": {"$in": upload.get("item_ids", [])}},
        {"$set": {"status": "approved", "approved_by": user["user_id"], "approved_at": now_iso, "updated_at": now_iso}},
    )
    await record_content_change(
        kind="menu", action="published", object_type="menu_upload", object_id=upload_id,
        actor=staff_actor(user), ingest_id=upload_id,
        before={"status": upload.get("status")},
        after={"status": "approved", "published_item_count": len(upload.get("item_ids", [])),
               "superseded_item_ids": superseded_ids})
    for old_id in superseded_ids:
        await record_content_change(
            kind="menu", action="superseded", object_type="menu_item", object_id=old_id,
            actor=staff_actor(user), ingest_id=upload_id,
            before={"status": "approved"}, after={"status": "superseded", "replaced_by_upload": upload_id})
    return await db.menu_uploads.find_one({"upload_id": upload_id}, {"_id": 0})
