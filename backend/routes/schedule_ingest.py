"""Schedule/activities email ingestion - the same "email is transport, not
the domain model" adapter boundary as backend/routes/menu_ingest.py, applied
to the resident-programs/activities calendar instead of the daily menu.

No real mailbox is configured yet (matching menu_ingest.py's own state), so
this exposes a dev-test ingestion endpoint that takes a raw email BODY
exactly the way a real inbound-email adapter eventually would. Swapping the
dev-test trigger for a real IMAP/webhook listener later is a transport
change only - the parsing logic below does not move.

IMPORTANT ARCHITECTURAL DIFFERENCE FROM menu_ingest.py, BY DESIGN:
MenuItem/MenuUpload have a draft -> approved status field and a batch
approve endpoint; ScheduleItem (backend/models.py) does NOT have any
status/approval concept - it is plain staff-entered CRUD (see
backend/routes/schedule.py). Inventing a draft/approve pipeline for
schedule items that the schema doesn't support would be a bigger, riskier
change than "add an email front-end for existing CRUD," so this module does
NOT do that. Parsed activities are created directly as live ScheduleItem
rows (source="email_dev_test") in one step, gated by the same staff/admin/
owner auth check POST /schedule already uses. There is no
/schedule/ingest/uploads or /approve endpoint here - if that gap ever
becomes a real problem (e.g. staff want to review before publishing), it
needs a schema change to ScheduleItem first, not a workaround here.

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

from models import ScheduleItem, ScheduleCategory
from deps import db, get_current_user

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


@router.post("/dev-test")
async def ingest_dev_test(body: dict, user=Depends(get_current_user)):
    """Simulates 'a weekly activities calendar email arrived' for
    development/acceptance testing, without a real mailbox. Body:
    {raw_text, source_ref?}. See module docstring for the expected format -
    dates are explicit per-day headers inside raw_text itself, not a single
    top-level field, since one email here typically covers a whole week.

    No draft/approve step (see module docstring) - parsed activities are
    created directly as live ScheduleItem rows, same auth gate as
    POST /schedule."""
    if user.get("role") not in ("admin", "owner", "staff"):
        raise HTTPException(status_code=403, detail="Staff required")
    raw_text = (body.get("raw_text") or "")[:16000]
    if not raw_text.strip():
        raise HTTPException(status_code=400, detail="raw_text is required")

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

    created = []
    for it in parsed_items:
        si = ScheduleItem(
            date=it["date"], time_label=it["time_label"], title=it["title"],
            description=it["description"], category=it["category"],
            source="email_dev_test", created_by=user["user_id"],
        )
        doc = si.model_dump()
        doc["created_at"] = doc["created_at"].isoformat()
        doc["updated_at"] = doc["updated_at"].isoformat()
        await db.schedule_items.insert_one(doc)
        doc.pop("_id", None)
        created.append(doc)

    return {
        "source": "email_dev_test",
        "source_ref": body.get("source_ref"),
        "created_count": len(created),
        "created": created,
        "skipped_lines": skipped_lines,
        "notes": notes,
    }
