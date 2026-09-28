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


def _sched(view: dict) -> str:
    label = view.get("scheduled_time_label")
    date = view.get("scheduled_date")
    if not label and not date:
        return ""
    return " Planned for " + " on ".join(x for x in (label, date) if x) + "."


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
    return {"lifecycle": lifecycle, "opened_age": opened_age, "spoken": spoken}
