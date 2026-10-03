"""Append-only transition history for StaffTask (ENGINEERING_CONTRACT.md
decision 6) - the task-side counterpart of Alert.event_log[].

Every lifecycle transition and every staff note on a request is PUSHED
onto staff_tasks.event_log, never rewritten, so "what happened between X
and Y" survives later changes: a completion note no longer erases the
progress notes before it, and a re-assignment no longer erases who held
the task first. Entry shape extends Alert's {at, field, from, to} with the
actor, plus `text` for notes:

    {"at", "field", "from", "to", "to_name", "by", "by_name", "text"}

field is one of: "status", "acknowledged", "assigned_to", "note",
"re_request". Tasks that predate this field simply have a shorter log -
nothing is backfilled (decision 6: no fabricated history).

This is internal state history. Receipts (routes/receipts.py) stay the
record of externally observable side effects.
"""
from typing import Any, Optional

from deps import db
from models import now_utc


def task_event(
    field: str,
    *,
    user: Optional[dict] = None,
    frm: Any = None,
    to: Any = None,
    to_name: Optional[str] = None,
    text: Optional[str] = None,
    by: Optional[str] = None,
    by_name: Optional[str] = None,
    receipt_id: Optional[str] = None,
) -> dict:
    """Build one event_log entry. `user` is the authenticated staff user;
    pass `by`/`by_name` instead for non-user actors (e.g. "resident").
    `receipt_id` links the entry to the receipt that records it (SIM-0),
    so history and receipts can be checked against each other."""
    entry: dict = {"at": now_utc().isoformat(), "field": field}
    if frm is not None:
        entry["from"] = frm
    if to is not None:
        entry["to"] = to
    if to_name is not None:
        entry["to_name"] = to_name
    if text is not None:
        entry["text"] = text
    entry["by"] = (user or {}).get("user_id") or by
    entry["by_name"] = (user or {}).get("name") or by_name
    if receipt_id:
        entry["receipt_id"] = receipt_id
    return entry


async def update_task_with_history(task_id: str, set_fields: Optional[dict], entries: list[dict]) -> None:
    """Apply a $set and append its event_log entries in ONE write, so the
    task's current fields and its history can never disagree."""
    update: dict = {}
    if set_fields:
        update["$set"] = set_fields
    if entries:
        update["$push"] = {"event_log": {"$each": entries}}
    if update:
        await db.staff_tasks.update_one({"task_id": task_id}, update)


def latest_note_at(task: dict) -> Optional[str]:
    """When the task's current note (`notes`) was written, from event_log.
    None for a note written before event_log existed - never guessed."""
    if not task.get("notes"):
        return None
    times = [e.get("at") for e in task.get("event_log") or [] if e.get("field") == "note"]
    return times[-1] if times else None


def times_asked(task: dict) -> int:
    """How many times the resident has asked: the first ask plus every
    re-request. The single source for "asked N times" wording."""
    return int(task.get("re_request_count") or 0) + 1
