"""Aria runtime conversation-vs-intent state (conversation substrate, Layer C).

Answers one narrow question, distinct from the other layers already built on
this branch: has *this specific call* already raised an actionable request,
and where did it leave off? Distinct from `aria_state` on the resident
assistance event (`dormant/active/muted_staff/dismissed` — event lifecycle,
not conversation state) and distinct from Layer E's operational snapshot
(`aria_operational_state.py` — facility-wide, all open work, keyed by
resident/room). This is keyed by `session_id`, so a reconnect or a
`session.update` mid-call sees what THIS call already did instead of
treating the session's mere existence as license to start or restart a task.

`conversation_session_id` on `db.staff_tasks` (see `resident_conversations.py`)
is the existing session-scoped action link — no new task-tracking table.
`db.conversations` (the existing turn store) is the transcript.

`actionable_intent_detected` (see docs/ARIA_CONVERSATION_SUBSTRATE.md,
"Separate conversation from intent") is a live, in-the-moment classification
the model itself makes while a request is still forming; it lasts a few
hundred ms before becoming `action_in_progress` (a tool fires) or dissolving
back into ordinary conversation, and leaves no row here to reconstruct after
the fact. This resolver derives the rest of the enum from what was actually
persisted for this session.

Read-only. No lifecycle transitions happen here — those stay in
`routes/resident_requests.py` / `routes/alerts.py`.
"""
from typing import Optional

from fastapi import APIRouter

from deps import db
from routes.aria_time import age_phrase as _age_label, parse_dt as _parse
from routes.aria_operational_state import task_lifecycle

router = APIRouter(prefix="/aria", tags=["realtime"])

STATES = (
    "conversation_active", "action_in_progress", "awaiting_required_detail",
    "action_completed", "conversation_resumed",
)

# How many turns of ordinary talk after an action closed before it counts as
# "the conversation moved on" (conversation_resumed) rather than "just closed"
# (action_completed, where a one-line confirmation is still natural).
RESUMED_AFTER_TURNS = 2


def _after(v, cutoff) -> bool:
    try:
        return _parse(v) > cutoff
    except Exception:
        return False


async def resolve_conversation_state(resident_id: Optional[str], session_id: Optional[str]) -> Optional[dict]:
    """What has THIS call (this session_id) done so far. `None` for a brand
    new session with nothing persisted yet — a fresh mint must not be told
    it is mid-conversation."""
    if not resident_id or not session_id:
        return None

    turns = await db.conversations.find(
        {"resident_id": resident_id, "session_id": session_id}, {"_id": 0},
    ).sort("created_at", 1).to_list(500)
    tasks = await db.staff_tasks.find(
        {"conversation_session_id": session_id}, {"_id": 0},
    ).sort("created_at", 1).to_list(20)

    if not turns and not tasks:
        return None

    open_tasks = [t for t in tasks if task_lifecycle(t) != "resolved"]
    resolved_tasks = [t for t in tasks if task_lifecycle(t) == "resolved"]

    if open_tasks:
        t = open_tasks[-1]
        return {
            "state": "action_in_progress",
            "ref": t.get("task_id"),
            "about": t.get("resident_words") or t.get("title") or "a request",
            "opened_age": _age_label(t.get("created_at")),
            "turn_count": len(turns),
        }

    if resolved_tasks:
        t = resolved_tasks[-1]
        done_at = t.get("completed_at") or t.get("created_at")
        turns_after = 0
        try:
            cutoff = _parse(done_at)
            turns_after = sum(1 for x in turns if _after(x.get("created_at"), cutoff))
        except Exception:
            pass
        state = "conversation_resumed" if turns_after > RESUMED_AFTER_TURNS else "action_completed"
        return {
            "state": state,
            "ref": t.get("task_id"),
            "about": t.get("resident_words") or t.get("title") or "a request",
            "handled_by": t.get("completed_by_name"),
            "turn_count": len(turns),
        }

    # `awaiting_required_detail` needs POSITIVE evidence that a request/routing
    # flow is mid-question — a trailing "?" alone is not it. An empathetic
    # "How are you feeling?" is ordinary conversation. The real signal: a
    # tool was engaged this call and the resident has not answered since.
    last_turn = turns[-1] if turns else None
    if (last_turn and last_turn.get("role") == "assistant"
            and (last_turn.get("content") or "").rstrip().endswith("?")
            and await _tool_awaiting_answer(session_id, turns)):
        return {"state": "awaiting_required_detail", "turn_count": len(turns)}

    return {"state": "conversation_active", "turn_count": len(turns)}


async def _tool_awaiting_answer(session_id: str, turns: list) -> bool:
    """True when a tool_call fired for this session and no resident turn has
    come since — i.e. Aria asked something a tool actually needs answered,
    not just a conversational question."""
    last_user_at = None
    for x in turns:
        if x.get("role") == "user" and x.get("created_at"):
            last_user_at = x["created_at"]
    try:
        tc = await db.realtime_diagnostics.find_one(
            {"session_id": session_id, "event_type": "tool_call"},
            {"_id": 0, "created_at": 1}, sort=[("created_at", -1)],
        )
    except Exception:
        return False
    if not tc or not tc.get("created_at"):
        return False
    if last_user_at is None:
        return True
    return _after(tc["created_at"], _parse(last_user_at))


_GUIDANCE = {
    "action_in_progress": (
        "You already have a request in motion in this same call ({about}, "
        "opened {opened_age}). If they bring it up again, do not file a "
        "second one — refer to the one already filed."
    ),
    "awaiting_required_detail": (
        "You already asked a routing question in this same call and are "
        "waiting on their answer. Do not ask it again — listen for what "
        "they say and use it."
    ),
    "action_completed": (
        "You already handled this in the same call ({about}{handled_by_suffix})."
        " You're back in ordinary conversation now — do not restart the "
        "request or re-explain it unless they ask."
    ),
    "conversation_resumed": (
        "Earlier in this same call you already handled {about}. That is "
        "done — this is just the conversation continuing, not a new "
        "workflow."
    ),
}


def _e_still_open(ref: Optional[str], operational_state: Optional[dict]) -> Optional[bool]:
    """Does Layer E's already-resolved snapshot still show `ref` as open work?
    None = E has no opinion (empty/absent snapshot) — defer to Layer C."""
    if not ref or not operational_state:
        return None
    items = (operational_state.get("current") or []) + (operational_state.get("background") or [])
    open_refs = {i.get("ref") for i in items if i.get("lifecycle") not in ("resolved", "answered")}
    if not open_refs:
        return None
    return ref in open_refs


def render_conversation_state_block(cs: Optional[dict], operational_state: Optional[dict] = None) -> str:
    """Empty string for a fresh call or ordinary back-and-forth — this block
    exists only to stop the model from re-asking or re-filing something this
    same call already settled, so it says nothing when there is nothing to
    guard against.

    Layer E is authoritative on truth: if the operational snapshot says this
    call's task is no longer open, do not tell the model it is still "in
    motion" — fall back to the already-handled framing."""
    if not cs:
        return ""
    state = cs.get("state")
    if state == "action_in_progress" and _e_still_open(cs.get("ref"), operational_state) is False:
        state = "action_completed"
    template = _GUIDANCE.get(state)
    if not template:
        return ""
    handled_by = cs.get("handled_by")
    body = template.format(
        about=cs.get("about") or "their request",
        opened_age=cs.get("opened_age") or "earlier in this call",
        handled_by_suffix=f", {handled_by}" if handled_by else "",
    )
    return "\n\n## This call so far\n" + body + "\n"


@router.get("/conversation-state")
async def conversation_state(resident_id: Optional[str] = None, session_id: Optional[str] = None):
    """Public — same trust model as the other resident-facing realtime
    inspection endpoints (kiosk-local, scoped to one resident + one session).
    Lets a call verify what Aria believes this specific session has already
    done without guessing from the raw transcript."""
    return await resolve_conversation_state(resident_id, session_id)
