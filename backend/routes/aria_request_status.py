"""Authoritative spoken status of a staff request (conversation substrate).

Step 1 of "current state wins": the resident-request tools
(`check_request_status`, the `request_staff_help` duplicate branch) must
describe a request with the SAME lifecycle vocabulary Layer E uses in the
"What's actually happening right now" block, so the tool result and the
context cannot contradict each other.

This is the one place that turns a `db.staff_tasks` row into
`{lifecycle, opened_age, spoken}`. It reuses `task_lifecycle` (Layer E) and
`age_phrase` (Layer B/E) — no independent interpretation, no re-query.
"""
from typing import Optional

from routes.aria_operational_state import task_lifecycle
from routes.aria_time import age_phrase
from routes.facility_local_time import facility_local
from routes.task_history import latest_note_at


def _owner(task: dict) -> Optional[str]:
    return task.get("assigned_to_name") or task.get("assigned_name")


def _sched(task: dict) -> str:
    """The planned visit window. Called with the raw staff_tasks row (fields
    requested_for_*); the resident view's names (scheduled_*) are accepted too
    so either shape speaks the window. Before 2026-10-11 only the view names
    were read, so a planned window was never spoken."""
    label = task.get("requested_for_time_label") or task.get("scheduled_time_label")
    date = task.get("requested_for_date") or task.get("scheduled_date")
    if not label and not date:
        return ""
    out = " Planned for " + " on ".join(x for x in (label, date) if x)
    who = task.get("provider_name")
    kind = task.get("discipline")
    if who and kind:
        out += f" with {who} ({kind})"
    elif who:
        out += f" with {who}"
    elif kind:
        out += f" ({kind})"
    if task.get("location"):
        out += f" at {task['location']}"
    return out + "."


def _note(task: dict, tz: Optional[str], lead: str) -> str:
    """The current staff note, with when it was written when that is known
    (from event_log). A note older than event_log is spoken without a time,
    never with an invented one."""
    text = (task.get("latest_update") or task.get("notes") or "").strip().rstrip(".")
    if not text:
        return ""
    when = facility_local(latest_note_at(task), tz) if tz else None
    stamp = f" ({when['label']})" if when else ""
    return f" {lead}{stamp}: {text}."


def items_text(items: list) -> str:
    """'2 × towels, 1 × warm blanket' - only what the request recorded."""
    return ", ".join(f"{i.get('quantity', 1)} × {i.get('item')}" for i in items)


def request_status_view(task: dict, tz: Optional[str] = None) -> dict:
    """`task` is a raw staff_tasks doc (it carries event_log, needed for the
    note time). `tz` (facility timezone) enables the note's time label."""
    lifecycle = task_lifecycle(task)
    opened = task.get("created_at")
    opened_age = age_phrase(opened) if opened else "at an unknown time"
    what = (task.get("what_for") or task.get("resident_words") or task.get("description")
            or task.get("title") or "your request")
    owner = _owner(task)

    if lifecycle == "resolved":
        who = task.get("completed_by_name") or owner
        spoken = f"That one — {what} — has been taken care of{f' by {who}' if who else ''}."
        spoken += _note(task, tz, "Their note")
    elif task.get("needs_review"):
        spoken = ("Staff weren't able to finish it, so a supervisor has been asked to look at it. "
                  f"It's still open.{_sched(task)}")
    elif lifecycle == "in_progress":
        spoken = f"{owner or 'Someone'} is working on it now.{_sched(task)}"
        spoken += _note(task, tz, "Latest note")
    elif lifecycle == "acknowledged":
        if owner:
            spoken = f"{owner} has taken it on — work hasn't started yet.{_sched(task)}"
        else:
            spoken = f"Staff have seen it — not finished yet.{_sched(task)}"
        spoken += _note(task, tz, "Latest note")
    else:  # open
        spoken = (f"It's still open — you raised it {opened_age}, and no one has "
                  f"picked it up yet.{_sched(task)}")
        if task.get("unclaimed_escalated_at"):
            spoken += " Because no one has taken it, it has been flagged to a supervisor."
    if task.get("items"):   # supplies/linens: say exactly what was asked for, in every state
        spoken += f" Asked for: {items_text(task['items'])}."
    return {"lifecycle": lifecycle, "opened_age": opened_age, "spoken": spoken}
