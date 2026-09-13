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


def _by(view: dict) -> str:
    who = view.get("assigned_to_name") or view.get("assigned_name") or view.get("completed_by_name")
    return f" ({who})" if who else ""


def _sched(view: dict) -> str:
    label = view.get("scheduled_time_label")
    date = view.get("scheduled_date")
    if not label and not date:
        return ""
    return " Planned for " + " on ".join(x for x in (label, date) if x) + "."


def request_status_view(task: dict) -> dict:
    """`task` is a raw staff_tasks doc OR an already-projected resident view
    (both carry `status`/`acknowledged_at`/`created_at`/schedule fields)."""
    lifecycle = task_lifecycle(task)
    opened = task.get("created_at")
    opened_age = age_phrase(opened) if opened else "at an unknown time"
    what = (task.get("what_for") or task.get("resident_words") or task.get("description")
            or task.get("title") or "your request")
    upd = (task.get("latest_update") or task.get("notes") or "").strip().rstrip(".")

    if lifecycle == "resolved":
        spoken = f"That one — {what} — has been taken care of{_by(task)}."
    elif lifecycle == "in_progress":
        spoken = f"Someone is working on it now{_by(task)}.{_sched(task)}"
    elif lifecycle == "acknowledged":
        spoken = f"Staff have seen it{_by(task)} — not finished yet.{_sched(task)}"
        if upd:
            spoken += f" Latest from them: {upd}."
    else:  # open
        spoken = (f"It's still open — you raised it {opened_age}, and no one has "
                  f"picked it up yet.{_sched(task)}")
    return {"lifecycle": lifecycle, "opened_age": opened_age, "spoken": spoken}
