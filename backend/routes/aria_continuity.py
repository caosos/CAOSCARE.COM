"""Aria cross-session continuity (conversation substrate, Layer B).

The "I thought I just told you" problem: every Realtime session builds its
prompt from resident_id only, and db.conversations is write-only in that
path, so a new session begins with zero memory of the one 3 minutes ago
(Room 214 sessions rt_8qt5gap4 -> rt_1niff83x -> rt_bnpqsque).

This assembles a compact CONTINUITY package from the records that already
exist (db.conversations turns + db.realtime_diagnostics end reasons) - no
parallel history system. It is BASELINE, not WORKFLOW:

  * it recaps what was recently *said*, not what is *active*;
  * it never marks an old task open - current operational truth is Layer E
    (routes/aria_operational_state.py), and the block points at it;
  * it excludes anything outside a recency window, and anything for another
    resident;
  * it is plain text, provider-independent - no GPT/Claude session state.

Economics: one indexed query + an in-memory trim. The rendered block is
hard-capped (see _TOTAL_CHAR_CAP) regardless of how long the prior
conversations were.
"""
from typing import Optional

from fastapi import APIRouter

from deps import db
from routes.aria_time import age_phrase, parse_dt

router = APIRouter(prefix="/aria", tags=["realtime"])

# Only sessions whose LAST turn is within this many hours are continuity.
# Older than this, a recap is intrusion, not help.
CONTINUITY_WINDOW_HOURS = 18
MAX_PRIOR_SESSIONS = 3
MAX_TURNS_PER_SESSION = 12
_TOTAL_CHAR_CAP = 2200
_ASSISTANT_TRIM = 180

# User turns that carry no referent worth recapping.
_TRIVIAL = {
    "", ".", "..", "...", "mm", "mmm", "hmm", "hm", "uh", "um", "hi", "hello",
    "hey", "yeah", "yes", "no", "ok", "okay", "sure", "thanks", "thank you",
    "bye", "goodbye", "what", "huh", "aria", "arya",
}
# Diagnostic end reasons that mean the resident did NOT close the call.
_UNFINISHED_ENDS = {
    "companion_timeout", "datachannel_closed", "datachannel_error",
    "realtime_error", "pc_disconnected", "setup_failed", None,
}


def _norm(s: str) -> str:
    return " ".join((s or "").split())


def _is_trivial(content: str) -> bool:
    t = _norm(content).lower().strip(" .,!?")
    return t in _TRIVIAL or len(t) <= 2


async def _end_reason(session_id: str) -> Optional[str]:
    row = await db.realtime_diagnostics.find_one(
        {"session_id": session_id, "event_type": "session_ended"},
        {"_id": 0, "meta": 1}, sort=[("created_at", -1)],
    )
    return ((row or {}).get("meta") or {}).get("reason")


def _compact_turns(turns: list[dict], name: str) -> list[str]:
    """Keep the resident's substantive lines verbatim (that is what 'that'
    and 'the other one' point back to); keep only trimmed, non-greeting
    assistant lines for grounding. Bias to the TAIL - the end of the
    conversation is what a follow-up refers to."""
    lines: list[str] = []
    last_user = None
    for t in turns:
        role = t.get("role")
        content = _norm(t.get("content"))
        if not content:
            continue
        if role == "user":
            if _is_trivial(content) or content.lower() == (last_user or "").lower():
                continue
            last_user = content
            lines.append(f"{name}: {content}")
        elif role == "assistant":
            low = content.lower()
            if low.startswith(("good morning", "good afternoon", "good evening", "hello", "hi ")):
                continue
            lines.append(f"you: {content[:_ASSISTANT_TRIM]}" + ("…" if len(content) > _ASSISTANT_TRIM else ""))
    return lines[-MAX_TURNS_PER_SESSION:]


async def resolve_continuity(
    resident_id: Optional[str],
    current_session_id: Optional[str] = None,
    room: Optional[str] = None,
) -> dict:
    """Compact recap of the resident's recent prior sessions. Empty when
    there is nothing recent - a fresh session then starts on baseline
    alone, inside no workflow."""
    if not resident_id:
        return {"has_continuity": False, "sessions": []}
    try:
        await db.conversations.create_index(
            [("resident_id", 1), ("created_at", -1)], name="continuity_lookup",
        )
    except Exception:
        pass

    rows = await db.conversations.find(
        {"resident_id": resident_id}, {"_id": 0, "session_id": 1, "role": 1,
                                       "content": 1, "created_at": 1},
    ).sort("created_at", -1).to_list(400)

    by_session: dict[str, list] = {}
    for r in rows:
        sid = r.get("session_id") or "unknown"
        if sid == current_session_id:
            continue
        by_session.setdefault(sid, []).append(r)

    # newest session first, by its most recent turn
    ordered = sorted(by_session.items(),
                     key=lambda kv: kv[1][0]["created_at"], reverse=True)

    out: list[dict] = []
    for sid, s_rows in ordered:
        if len(out) >= MAX_PRIOR_SESSIONS:
            break
        s_rows = list(reversed(s_rows))  # chronological
        last_at = s_rows[-1]["created_at"]
        try:
            secs = (parse_dt(last_at)).timestamp()
        except Exception:
            continue
        from models import now_utc
        if (now_utc().timestamp() - secs) > CONTINUITY_WINDOW_HOURS * 3600:
            break  # everything older is outside the window too (sorted)
        end_reason = await _end_reason(sid)
        out.append({
            "session_id": sid,
            "age_phrase": age_phrase(last_at),
            "ended_at": last_at,
            "end_reason": end_reason,
            "unfinished": end_reason in _UNFINISHED_ENDS,
            "turn_count": len(s_rows),
            "_rows": s_rows,
        })

    return {"has_continuity": bool(out), "sessions": out}


_HEADER = (
    "## Where you and {name} were  (recent conversation — context, not a task)\n"
    "This is only what was recently *said*. It is NOT an active request and NOT "
    "an unfinished job of yours. Do not reopen these topics, recap them aloud, "
    "or offer to \"continue\" — follow them only if {name} raises them. Greet "
    "{name} simply; this recap is not an opener. If anything below mentions a "
    "call, a request, or a nurse coming, the \"What's actually happening right "
    "now\" section is the authoritative current status — not this recap.\n"
)


def render_continuity_block(state: Optional[dict], name: str = "them") -> str:
    if not state or not state.get("has_continuity"):
        return ""
    parts = ["\n\n" + _HEADER.format(name=name)]
    budget = _TOTAL_CHAR_CAP
    for s in state["sessions"]:
        tail = " — the call dropped before a goodbye; {n} may pick this back up".format(n=name) \
            if s["unfinished"] else " — ended when {n} was done".format(n=name)
        head = f"\n### {s['age_phrase'].capitalize()}{tail}\n"
        body_lines = _compact_turns(s["_rows"], name)
        chunk = head + "\n".join(body_lines) + "\n"
        if len(chunk) > budget:
            break
        budget -= len(chunk)
        parts.append(chunk)
    return "".join(parts)


@router.get("/continuity")
async def continuity(
    resident_id: Optional[str] = None,
    current_session_id: Optional[str] = None,
    room: Optional[str] = None,
):
    """Public — resident/room-scoped, same trust model as the other
    resident-facing realtime endpoints. Inspection/debug surface for the
    continuity package the session mint assembles."""
    state = await resolve_continuity(resident_id, current_session_id, room)
    # drop the raw rows from the wire view
    return {"has_continuity": state["has_continuity"],
            "sessions": [{k: v for k, v in s.items() if k != "_rows"}
                         for s in state["sessions"]]}
