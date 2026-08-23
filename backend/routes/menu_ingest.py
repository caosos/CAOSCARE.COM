"""Menu email ingestion - the adapter boundary described in the Terminal 8
handoff: email is source/provenance/transport, never the domain model.

No real mailbox is configured yet (still open per the Terminal 8 living
build log), so this exposes a dev-test ingestion endpoint that takes a raw
email BODY exactly the way a real inbound-email adapter eventually would,
and runs it through the same parse -> draft -> approve -> live pipeline.
Swapping the dev-test trigger for a real IMAP/webhook listener later is a
transport change only - this parsing/approval logic does not move.

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

router = APIRouter(prefix="/menu", tags=["menu"])

_SECTION_RE = re.compile(
    r"(breakfast|lunch|dinner|supper)\s*:?\s*\n?(.*?)(?=\n\s*(?:breakfast|lunch|dinner|supper)\s*:|\Z)",
    re.IGNORECASE | re.DOTALL,
)
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
        for raw_line in re.split(r"[\n,]", body):
            name = raw_line.strip(" \t-*•").strip()
            if name:
                items.append({"meal_period": meal, "item_name": name})
    if not found_meals:
        return [], "needs_review", "Could not find Breakfast/Lunch/Dinner section headers in the email body."
    missing = {"breakfast", "lunch", "dinner"} - found_meals
    if missing:
        return items, "needs_review", f"No section found for: {', '.join(sorted(missing))}."
    return items, "parsed", None


@router.post("/ingest/dev-test")
async def ingest_dev_test(body: dict, user=Depends(get_current_user)):
    """Simulates 'an email arrived' for development/acceptance testing,
    without a real mailbox. Body: {service_date, raw_text, source_ref?}.
    service_date is required explicitly rather than guessed from free text -
    real date-detection from an arbitrary email body is exactly the kind of
    fragile guessing this project avoids; a real email adapter would supply
    this from the message's own date or a clearly-labeled line, not regex
    over prose."""
    if user.get("role") not in ("admin", "owner", "staff"):
        raise HTTPException(status_code=403, detail="Staff required")
    service_date = body.get("service_date")
    raw_text = (body.get("raw_text") or "")[:8000]
    if not service_date or not raw_text.strip():
        raise HTTPException(status_code=400, detail="service_date and raw_text are required")

    parsed_items, parse_status, parse_notes = _parse_menu_email(raw_text)

    upload = MenuUpload(
        source="email_dev_test",
        source_ref=body.get("source_ref"),
        raw_text=raw_text,
        service_date=service_date,
        parse_status=parse_status,
        parse_notes=parse_notes,
        created_by=user["user_id"],
    )
    upload_doc = upload.model_dump()
    upload_doc["created_at"] = upload_doc["created_at"].isoformat()

    item_ids = []
    for it in parsed_items:
        mi = MenuItem(
            date=service_date, meal_period=it["meal_period"], item_name=it["item_name"],
            source="email_dev_test", upload_id=upload_doc["upload_id"],
        )
        mi_doc = mi.model_dump()
        mi_doc["created_at"] = mi_doc["created_at"].isoformat()
        mi_doc["updated_at"] = mi_doc["updated_at"].isoformat()
        await db.menu_items.insert_one(mi_doc)
        item_ids.append(mi_doc["menu_id"])

    upload_doc["item_ids"] = item_ids
    await db.menu_uploads.insert_one(dict(upload_doc))
    upload_doc.pop("_id", None)
    return upload_doc


@router.get("/uploads")
async def list_uploads(service_date: Optional[str] = None, user=Depends(get_current_user)):
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
    if user.get("role") not in ("admin", "owner", "staff"):
        raise HTTPException(status_code=403, detail="Staff required")
    upload = await db.menu_uploads.find_one({"upload_id": upload_id}, {"_id": 0})
    if not upload:
        raise HTTPException(status_code=404, detail="Upload not found")
    now_iso = now_utc().isoformat()

    meal_periods = set(
        i["meal_period"] for i in await db.menu_items.find(
            {"menu_id": {"$in": upload.get("item_ids", [])}}, {"_id": 0, "meal_period": 1}
        ).to_list(200)
    )
    if meal_periods:
        await db.menu_items.update_many(
            {
                "date": upload["service_date"],
                "meal_period": {"$in": list(meal_periods)},
                "status": "approved",
                "menu_id": {"$nin": upload.get("item_ids", [])},
            },
            {"$set": {"status": "superseded", "updated_at": now_iso}},
        )

    await db.menu_uploads.update_one(
        {"upload_id": upload_id},
        {"$set": {"status": "approved", "approved_by": user["user_id"], "approved_at": now_iso}},
    )
    await db.menu_items.update_many(
        {"menu_id": {"$in": upload.get("item_ids", [])}},
        {"$set": {"status": "approved", "approved_by": user["user_id"], "approved_at": now_iso, "updated_at": now_iso}},
    )
    return await db.menu_uploads.find_one({"upload_id": upload_id}, {"_id": 0})
