"""Aria operational-state authority (conversation substrate, Layer E).

One place that answers "what is actually happening for this resident right
now" by unifying the two operational subsystems that used to speak past
each other:

  * the resident's open assistance **event** (`db.alerts` — opened by an RF
    pendant / kiosk button / `call_for_help`), and
  * the resident's open staff **requests** (`db.staff_tasks` — created by
    `request_staff_help`).

Room 214 evidence (`docs/ROOM_214_CONVERSATION_EVIDENCE_2026-09-08.md`,
Part 4 #1): `check_request_status` read only `staff_tasks` and returned the
*oldest* open one, so during a bleeding emergency Aria reported "it's for
needs help using the bathroom", and its spoken string dropped `created_at`
so Aria could not answer "when was that made". This module carries real
lifecycle + timestamps + who, and tags each item `current` vs `background`
so Aria speaks from present state instead of reading a stale queue.

Read-only. No lifecycle transitions happen here — that stays in
`routes/alerts.py`, `routes/alert_lifecycle_events.py`,
`routes/resident_requests.py`.
"""
from typing import Optional

from fastapi import APIRouter, HTTPException

from deps import db
from models import now_utc
from routes.aria_time import age_phrase as _age_label, parse_dt as _parse

router = APIRouter(prefix="/aria", tags=["realtime"])

# How far back a resolved item is still worth mentioning as shared context
# ("Barbara's was handled"). Older than this and it is just history.
RECENT_RESOLVED_HOURS = 12
OPEN_ALERT_STATUSES = ["active", "acknowledged"]
OPEN_TASK_STATUSES = ["pending", "in_progress"]


def _iso(v) -> Optional[str]:
    return v.isoformat() if hasattr(v, "isoformat") else (v or None)


def _alert_lifecycle(a: dict) -> str:
    """Normalize a staff-facing Alert into a single conversational lifecycle
    word. Precedence: a resolved/answered event is that, regardless of
    earlier states."""
    if a.get("status") == "resolved" or a.get("resolved_at"):
        return "resolved"
    if a.get("live_line_state") == "connected" or a.get("live_line_state") == "answered":
        return "answered"
    if a.get("status") == "acknowledged" or a.get("acknowledged_at"):
        return "acknowledged"
    if (a.get("escalation_level") or 0) >= 1:
        return "escalated"
    return "open"


def task_lifecycle(t: dict) -> str:
    if t.get("status") == "completed":
        return "resolved"
    if t.get("status") == "in_progress":
        return "in_progress"
    if t.get("acknowledged_at"):
        return "acknowledged"
    return "open"


def _alert_view(a: dict, current: bool) -> dict:
    opened = _iso(a.get("created_at"))
    lifecycle = _alert_lifecycle(a)
    handled_by = a.get("resolved_by") or a.get("acknowledged_by")
    changed = _iso(a.get("resolved_at") or a.get("acknowledged_at"))
    return {
        "kind": "assistance_event",
        "ref": a.get("alert_id"),
        "about": (a.get("resident_stated_reason") or a.get("ai_summary")
                  or a.get("category") or a.get("message") or "an assistance request"),
        "lifecycle": lifecycle,
        "acknowledged": lifecycle not in ("open", "escalated"),
        "handled_by": handled_by,
        "opened_at": opened,
        "opened_age": _age_label(opened),
        "state_changed_at": changed,
        "press_count": a.get("press_count", 1),
        "severity": a.get("severity"),
        "relevance": "current" if current else "background",
    }


def _task_view(t: dict, current: bool) -> dict:
    opened = _iso(t.get("created_at"))
    lifecycle = task_lifecycle(t)
    return {
        "kind": "staff_request",
        "ref": t.get("task_id"),
        "about": (t.get("resident_words") or t.get("description") or t.get("title")
                  or f"a {t.get('category', 'staff')} request"),
        "category": t.get("category"),
        "lifecycle": lifecycle,
        "acknowledged": lifecycle not in ("open",),
        "handled_by": t.get("assigned_name") or t.get("completed_by_name"),
        "opened_at": opened,
        "opened_age": _age_label(opened),
        "scheduled_date": t.get("requested_for_date"),
        "scheduled_time_label": t.get("requested_for_time_label"),
        "latest_update": t.get("notes") or "",
        "re_request_count": t.get("re_request_count", 0),
        "relevance": "current" if current else "background",
    }


SPEAK_GUIDANCE = (
    "This is shared context, not a script. Speak from the CURRENT lifecycle of "
    "each item, never from an old notification. Do not read this as a list or "
    "ask whether they want to review their requests just because items exist. "
    "Only raise a `background` item if the conversation naturally leads there. "
    "You MAY say when something was opened using its `opened_age` (e.g. 'the one "
    "you pressed about earlier today'); never invent a clock time. If an item is "
    "`resolved` or `answered`, do not still speak of it as waiting."
)


async def resolve_operational_state(
    resident_id: Optional[str] = None,
    room: Optional[str] = None,
    alert_id: Optional[str] = None,
) -> dict:
    """Authoritative 'what is happening for this resident right now'.

    `alert_id` (the event that brought Aria into this conversation, when
    there is one) is what makes an item `current` rather than `background`.
    """
    if not resident_id and not room:
        raise HTTPException(status_code=400, detail="resident_id or room required")

    scope = {"resident_id": resident_id} if resident_id else {"room": room}
    now = now_utc()

    open_alerts = await db.alerts.find(
        {**scope, "status": {"$in": OPEN_ALERT_STATUSES}}, {"_id": 0},
    ).sort("created_at", -1).to_list(20)

    # The current event: the one named by alert_id, else — only if there is
    # exactly one — the single open event. Ambiguity stays ambiguous rather
    # than guessing the newest is "the" one.
    current_ref = alert_id
    if not current_ref and len(open_alerts) == 1:
        current_ref = open_alerts[0].get("alert_id")

    open_tasks = await db.staff_tasks.find(
        {**scope, "status": {"$in": OPEN_TASK_STATUSES},
         "source": {"$in": ["aria_voice", "kiosk_button"]}}, {"_id": 0},
    ).sort("created_at", -1).to_list(20)

    cutoff = (now.timestamp() - RECENT_RESOLVED_HOURS * 3600)
    recent_resolved: list = []
    for a in await db.alerts.find(
        {**scope, "status": "resolved"}, {"_id": 0},
    ).sort("resolved_at", -1).to_list(10):
        ts = a.get("resolved_at")
        try:
            if _parse(ts).timestamp() >= cutoff:
                recent_resolved.append(_alert_view(a, current=False))
        except Exception:
            continue

    items = [_alert_view(a, a.get("alert_id") == current_ref) for a in open_alerts]
    items += [_task_view(t, False) for t in open_tasks]

    current = [i for i in items if i["relevance"] == "current"]
    background = [i for i in items if i["relevance"] == "background"]

    return {
        "as_of": now.isoformat(),
        "resident_id": resident_id,
        "room": room,
        "current_event_ref": current_ref,
        "has_open_work": bool(items),
        "current": current,
        "background": background,
        "recently_resolved": recent_resolved,
        "speak_guidance": SPEAK_GUIDANCE,
    }


@router.get("/operational-state")
async def operational_state(
    resident_id: Optional[str] = None,
    room: Optional[str] = None,
    alert_id: Optional[str] = None,
):
    """Public — same trust model as the other resident-facing realtime
    endpoints (kiosk-local, scoped to one resident or one room, never a
    global query). Lets the kiosk/Aria answer 'is anyone coming', 'when did
    I ask', 'was that handled' from real state."""
    return await resolve_operational_state(resident_id, room, alert_id)
