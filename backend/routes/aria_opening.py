"""How a call opens (Michael, 2026-10-12): after "Hey Aria" she answers the way
a person answers their name - one short line with the resident's name - not
the same long time-of-day greeting every call; and she never opens the same
way as her previous call. The previous call's first line is read from
db.conversations (the turns already saved for continuity); nothing new is
stored. Best-effort: a lookup failure only drops the "don't repeat" hint.
"""
from typing import Optional

from deps import db
from models import now_utc
from routes.aria_time import parse_dt

_MAX_QUOTE = 200
async def resolve_opening(resident_id: Optional[str], session_id: Optional[str], trigger_source: Optional[str]) -> dict:
    opening = {"wake": trigger_source == "wake_word", "last_opening": None, "minutes_since_last": None}
    if not resident_id:
        return opening
    try:
        q = {"resident_id": resident_id, "role": "assistant"}
        if session_id:
            q["session_id"] = {"$ne": session_id}
        latest = await db.conversations.find_one(q, {"session_id": 1, "created_at": 1}, sort=[("created_at", -1)])
        if latest:
            try:
                opening["minutes_since_last"] = round((now_utc() - parse_dt(latest["created_at"])).total_seconds() / 60, 1)
            except Exception:
                pass
            first = await db.conversations.find_one(
                {"resident_id": resident_id, "session_id": latest["session_id"], "role": "assistant"},
                {"content": 1}, sort=[("created_at", 1)])
            text = " ".join(str((first or {}).get("content") or "").split())
            opening["last_opening"] = text[:_MAX_QUOTE] or None
    except Exception:
        pass
    return opening


def render_opening_block(opening: Optional[dict], name: str) -> str:
    """The '## How this call opens' prompt section ('' when nothing applies)."""
    if not opening:
        return ""
    lines = []
    if opening.get("wake"):
        lines.append(
            f"They just called you by name - \"Hey Aria\". Answer the way a person answers when "
            f"their name is called: one short line with their name - \"Hey, {name}.\", \"Yes, {name}?\", "
            f"\"I'm here, {name}.\" - then stop and listen. No time-of-day greeting, no \"take your time\", "
            f"no question about how they are and no lingering offer. Never mention when the prior "
            f"conversation happened. Carry prior context forward silently.")
    last = " ".join(str(opening.get("last_opening") or "").split())[:_MAX_QUOTE]
    if last:
        lines.append(f"Your previous call opened with: \"{last}\". Do not open the same way - vary your words.")
    if not lines:
        return ""
    return "## How this call opens\n" + "\n".join(lines) + "\n\n"
