"""Schedule/activities email ingestion - the same "email is transport, not
the domain model" adapter boundary as backend/routes/menu_ingest.py, applied
to the resident-programs/activities calendar instead of the daily menu.

REVIEW GATE: parsed activities are created as DRAFT ScheduleItem rows
sharing one `ingest_id`, and reach residents/Aria only when staff publish
that batch (POST /schedule/batches/{ingest_id}/publish, schedule.py). A
mis-parsed or wrong calendar therefore never goes live on its own - the
same stance the menu lane takes. Triggers: the real inbound-email webhook
(email_inbound.py), staff pasting a calendar (POST /schedule/ingest/paste),
and the dev-test endpoint the seed scripts use - all call
create_schedule_items(); only the provenance `source` differs.

EXPECTED EMAIL FORMAT (dev-test convention, designed for this module):
A weekly (or multi-day) activities calendar email body. Each day starts
its own header line containing an explicit ISO date - never inferred from
a bare weekday name, matching menu_ingest.py's stance that date-guessing
from free text is exactly the kind of fragile guessing this project avoids.
A weekday name may prefix the date for human readability but is decorative
only and is not what determines the date:

    Monday 2026-08-24:
    10:00 AM Chair Yoga - gentle stretching, Sunroom
    2:00 PM Bingo - Main activity room, prizes provided [activity]
    5:30 PM Staff shift change note [staff_hours]

    Tuesday 2026-08-25:
    9:30 AM Hymn Sing
    1:00 PM Movie Afternoon - "Casablanca", popcorn served
    3:00 PM Family Visiting Hours [facility_note]

Per-activity line grammar, one activity per line under its day header:

    [HH:MM AM/PM ]Title[ - description][ [category]]

- Leading time is optional free text, stored as-is in time_label (e.g.
  "10:00 AM"); omit it for an all-day/untimed note.
- Title is required; everything up to " - " or a trailing "[...]" tag.
- Description is optional, introduced by " - ".
- Category is optional, given as a bracketed tag matching one of
  ScheduleCategory's values: activity | facility_note | staff_hours.
  Defaults to "activity" when omitted. An unrecognized bracket tag is not
  guessed at - the line still gets created with the default category, and
  is reported back in `notes` so staff can see it needs a look.
- A line under a day header that doesn't resolve to a title at all
  (blank, or pure punctuation) is skipped and reported in `skipped_lines`
  rather than silently dropped or guessed into existence.

If no day header (explicit YYYY-MM-DD) is found anywhere in the body, the
whole request is rejected with 422 rather than silently creating nothing -
same "fail loudly instead of guessing" stance as menu_ingest.py.
"""
import re
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends

from models import ScheduleItem, ScheduleCategory, uid
from deps import db, get_current_user
from routes.actor_context import ActorContext
from routes.content_receipts import inbound_email_actor, record_content_change, staff_actor
from routes.service_content_access import SCHEDULE_DEPARTMENTS, require_content_editor

router = APIRouter(prefix="/schedule/ingest", tags=["schedule"])

_VALID_CATEGORIES = set(ScheduleCategory.__args__)  # {"activity", "facility_note", "staff_hours"}

# Day header: optional weekday-name prefix (decorative, ignored) + required
# explicit ISO date, optionally followed by a colon.
_DAY_HEADER_RE = re.compile(
    r"^[ \t]*(?:[A-Za-z]+,?[ \t]+)?(\d{4}-\d{2}-\d{2})[ \t]*:?[ \t]*$",
    re.MULTILINE,
)

# One activity line: optional leading time, required title, optional
# " - description", optional trailing "[category]" tag.
_LINE_RE = re.compile(
    r"^\s*(?:(\d{1,2}:\d{2}\s*[AaPp][Mm])\s+)?"   # 1: time_label (optional)
    r"([^\-\[\n]+?)"                               # 2: title (required, non-greedy)
    r"(?:\s*-\s*([^\[\n]+?))?"                     # 3: description (optional)
    r"(?:\s*\[(\w+)\])?"                           # 4: category tag (optional)
    r"\s*$"
)


def _split_day_blocks(raw_text: str) -> list[tuple[str, str]]:
    """Returns [(date, block_text), ...] for each day header found, block
    text running to the next header or end of the email body."""
    headers = list(_DAY_HEADER_RE.finditer(raw_text))
    blocks = []
    for i, m in enumerate(headers):
        start = m.end()
        end = headers[i + 1].start() if i + 1 < len(headers) else len(raw_text)
        blocks.append((m.group(1), raw_text[start:end]))
    return blocks


def _parse_schedule_email(raw_text: str) -> tuple[list[dict], list[str], list[str]]:
    """Returns (items, skipped_lines, notes). Each item is
    {date, time_label, title, description, category}. Deterministic,
    no model call - see module docstring for the exact line grammar."""
    items: list[dict] = []
    skipped_lines: list[str] = []
    notes: list[str] = []

    for date, block in _split_day_blocks(raw_text):
        for raw_line in block.splitlines():
            line = raw_line.strip(" \t-*•")
            if not line:
                continue
            m = _LINE_RE.match(line)
            title = (m.group(2).strip() if m else "").strip(" \t-*•")
            if not m or not title:
                skipped_lines.append(f"{date}: {raw_line.strip()}")
                continue
            time_label = m.group(1).strip() if m.group(1) else None
            description = m.group(3).strip() if m.group(3) else ""
            raw_category = m.group(4).strip().lower() if m.group(4) else None
            if raw_category and raw_category in _VALID_CATEGORIES:
                category = raw_category
            else:
                category = "activity"
                if raw_category:
                    notes.append(
                        f"{date}: unrecognized category tag '[{raw_category}]' on "
                        f"'{title}' - defaulted to 'activity'."
                    )
            items.append({
                "date": date, "time_label": time_label, "title": title,
                "description": description, "category": category,
            })
    return items, skipped_lines, notes


async def create_schedule_items(
    *, raw_text: str, source: str, source_ref: Optional[str] = None,
    created_by: Optional[str] = None, actor: Optional[ActorContext] = None,
) -> dict:
    """The one internal ingestion function for an activities/schedule
    calendar (emailed, pasted or dev-test) - parses raw_text and creates
    DRAFT ScheduleItem rows sharing one ingest_id. `source` is provenance only
    ("email_dev_test" | "email" | anything else a future caller
    supplies). Raises 422 if no day header is found at all (see module
    docstring) - the caller decides how to represent that (the dev-test
    endpoint lets the HTTPException propagate; the real inbound-email
    webhook catches it and records the message as needs_review instead
    of a hard failure, since a malformed real email should never 500)."""
    parsed_items, skipped_lines, notes = _parse_schedule_email(raw_text)
    if not parsed_items and not skipped_lines:
        raise HTTPException(
            status_code=422,
            detail=(
                "No day headers found (expected a line with an explicit "
                "YYYY-MM-DD date, e.g. 'Monday 2026-08-24:'). See "
                "schedule_ingest.py module docstring for the expected format."
            ),
        )

    ingest_id = uid("sched_ingest")
    created = []
    for it in parsed_items:
        si = ScheduleItem(
            date=it["date"], time_label=it["time_label"], title=it["title"],
            description=it["description"], category=it["category"], status="draft",
            source=source, source_ref=source_ref, ingest_id=ingest_id, created_by=created_by,
        )
        doc = si.model_dump()
        doc["created_at"] = doc["created_at"].isoformat()
        doc["updated_at"] = doc["updated_at"].isoformat()
        await db.schedule_items.insert_one(doc)
        doc.pop("_id", None)
        created.append(doc)

    await record_content_change(
        kind="schedule", action="uploaded", object_type="schedule_batch", object_id=ingest_id,
        actor=actor or inbound_email_actor(), ingest_id=ingest_id,
        after={"status": "draft", "source": source, "item_count": len(created),
               "dates": sorted({c["date"] for c in created})})
    return {
        "ingest_id": ingest_id,
        "status": "draft",
        "source": source,
        "source_ref": source_ref,
        "created_count": len(created),
        "created": created,
        "skipped_lines": skipped_lines,
        "notes": notes,
    }


@router.post("/dev-test")
async def ingest_dev_test(body: dict, user=Depends(get_current_user)):
    """Simulates 'a weekly activities calendar email arrived' for
    development/acceptance testing, without needing a real inbound
    email. Body: {raw_text, source_ref?}. See module docstring for the
    expected format - dates are explicit per-day headers inside raw_text
    itself, not a single top-level field, since one email here typically
    covers a whole week.

    Rows are drafts until the batch is published (see module docstring).
    The real inbound-email webhook (email_inbound.py) calls the same
    create_schedule_items() this endpoint calls."""
    require_content_editor(user, SCHEDULE_DEPARTMENTS)
    raw_text = (body.get("raw_text") or "")[:16000]
    if not raw_text.strip():
        raise HTTPException(status_code=400, detail="raw_text is required")

    return await create_schedule_items(
        raw_text=raw_text, source="email_dev_test",
        source_ref=body.get("source_ref"), created_by=user["user_id"], actor=staff_actor(user),
    )


@router.post("/paste")
async def ingest_paste(body: dict, user=Depends(get_current_user)):
    """Activities staff paste a weekly calendar (the schedule screen's
    "Paste a calendar"). Same parser and draft batch as an emailed
    calendar; source="staff_paste". Body: {raw_text}."""
    require_content_editor(user, SCHEDULE_DEPARTMENTS)
    raw_text = (body.get("raw_text") or "")[:16000]
    if not raw_text.strip():
        raise HTTPException(status_code=400, detail="raw_text is required")
    return await create_schedule_items(raw_text=raw_text, source="staff_paste",
                                       created_by=user["user_id"], actor=staff_actor(user))
