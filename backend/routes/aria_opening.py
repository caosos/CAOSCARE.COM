"""How a call opens (Michael, 2026-10-12): after "Hey Aria" she answers the way
a person answers their name - one short line with the resident's name - not
the same long time-of-day greeting every call; and she never opens the same
way as her recent calls. The recent calls' first lines are read from
db.conversations (the turns already saved for continuity); nothing new is
stored. Best-effort: a lookup failure only drops the "don't repeat" hint.

Repeats (aria-room-conversation-cleanup-002): three consecutive tap calls on
the scratch Room 214 copy all opened "I'm here, Michael." although the prompt
quoted the previous opening - the prompt itself suggested "I'm here" twice
(the night greeting note and the help-button line) and only said "vary your
words" against it. Now the block offers a few natural short openings and
leaves out any whose lead words a recent call already used, so the
suggestions rotate deterministically instead of relying on the model to vary.
"""
import re
from typing import Optional

from deps import db
from models import now_utc
from routes.aria_time import parse_dt

_MAX_QUOTE = 200
RECENT_CALLS = 3
_SCAN_ROWS = 200

# Natural short openings, in preference order. {n} is the resident's name.
WAKE_OPENINGS = ("Hey, {n}.", "Yes, {n}?", "I'm here, {n}.", "Hi, {n}.", "Mm-hm, {n}?")
TAP_OPENINGS = ("Hi, {n}.", "There you are, {n}.", "Hey there, {n}.", "Hello, {n}.", "I'm here, {n}.")
_SUGGEST = 3


async def resolve_opening(resident_id: Optional[str], session_id: Optional[str], trigger_source: Optional[str]) -> dict:
    opening = {"wake": trigger_source == "wake_word", "last_opening": None, "recent_openings": [],
               "minutes_since_last": None}
    if not resident_id:
        return opening
    try:
        q = {"resident_id": resident_id, "role": "assistant"}
        if session_id:
            q["session_id"] = {"$ne": session_id}
        rows = await db.conversations.find(q, {"session_id": 1, "created_at": 1}).sort(
            "created_at", -1).limit(_SCAN_ROWS).to_list(_SCAN_ROWS)
        sessions = []
        for r in rows:
            if r.get("session_id") and r["session_id"] not in sessions:
                sessions.append(r["session_id"])
            if len(sessions) == RECENT_CALLS:
                break
        if rows:
            try:
                opening["minutes_since_last"] = round((now_utc() - parse_dt(rows[0]["created_at"])).total_seconds() / 60, 1)
            except Exception:
                pass
        for sid in sessions:
            first = await db.conversations.find_one(
                {"resident_id": resident_id, "session_id": sid, "role": "assistant"},
                {"content": 1}, sort=[("created_at", 1)])
            text = " ".join(str((first or {}).get("content") or "").split())[:_MAX_QUOTE]
            if text:
                opening["recent_openings"].append(text)
        opening["last_opening"] = (opening["recent_openings"] or [None])[0]
    except Exception:
        pass
    return opening


def opening_lead(text: str, name: str) -> str:
    """The lead words of an opening's first sentence, without the name:
    "I'm here, Michael. If you want..." -> "i'm here"."""
    first = re.split(r"(?<=[.!?])\s", (text or "").strip(), maxsplit=1)[0]
    words = [w for w in re.findall(r"[a-z']+", first.lower().replace("\u2019", "'")) if w != (name or "").lower()]
    return " ".join(words[:2])


def suggested_openings(opening: dict, name: str, part_of_day: Optional[str] = None) -> list:
    """Up to three short openings whose lead differs from every recent call's opening."""
    pool = list(WAKE_OPENINGS) if opening.get("wake") else list(TAP_OPENINGS)
    if not opening.get("wake") and part_of_day and part_of_day != "night":
        pool.insert(1, f"Good {part_of_day}, {{n}}.")      # never "good night": it reads as a farewell
    used = {opening_lead(t, name) for t in (opening.get("recent_openings") or [opening.get("last_opening")]) if t}
    fresh = [o.format(n=name) for o in pool if opening_lead(o.format(n=name), name) not in used]
    return fresh[:_SUGGEST]


def render_opening_block(opening: Optional[dict], name: str, part_of_day: Optional[str] = None) -> str:
    """The '## How this call opens' prompt section ('' when nothing applies).

    It is the LAST section of the session instructions (realtime_companion_prompt
    puts any room-specific context before it): the call opens with a bare
    response.create, and the model answers whatever text it read last. With the
    Room 214 owner block last it opened with "Got it, I'm going with Michael.
    Nice and simple." (aria-room-followup-truth-001)."""
    if not opening:
        return ""
    lines = []
    examples = " / ".join(f'"{o}"' for o in suggested_openings(opening, name, part_of_day))
    if opening.get("wake"):
        lines.append(
            f"They just called you by name - \"Hey Aria\". Answer the way a person answers when "
            f"their name is called: one short line with their name - for example {examples} - then stop "
            f"and listen. No time-of-day greeting, no \"take your time\", "
            f"no question about how they are and no lingering offer. Never mention when the prior "
            f"conversation happened. Carry prior context forward silently.")
    else:
        lines.append(
            f"Open with one short, warm line with their name - for example {examples} - then leave "
            f"room for them to speak.")
    recent = [" ".join(str(t).split())[:_MAX_QUOTE] for t in (opening.get("recent_openings") or [opening.get("last_opening")]) if t]
    if recent:
        quoted = " / ".join(f'"{t}"' for t in recent)
        lines.append(f"Your most recent calls opened with: {quoted}. Start differently from every one of "
                     f"these - different first words, not the same line again.")
    # Last, so the final text before the bare greeting response.create is about the resident.
    lines.append(
        f"Your first words are spoken to {name}. Never reply to these instructions: no \"Got it\", "
        f"\"Sure thing\", \"Understood\" or \"Okay\" as an opener, never say which name you will use "
        f"or how you will sound, never narrate what you are about to do.")
    return "## How this call opens\n" + "\n".join(lines) + "\n\n"
