"""Guard against a real, confirmed failure (Chauncey / Room 304,
2026-08-23 incident report): the model invented a specific appointment
time ("10 o'clock") the resident never said, and it became part of a
real, staff-visible task (task_705cbcd180f1 - kept on file as evidence,
not deleted).

Deliberately small - not a general provenance framework. Checks one
concrete, previously-proven-dangerous thing: does a clock-time claim in an
operational-request free-text field actually appear in something the
resident said this session? Backend-enforced (not prompt wording alone)
per Michael's explicit instruction that a syntactically valid tool call
must not be trusted just because it parses.
"""
import re
from typing import Optional

from deps import db

_TIME_CLAIM_RE = re.compile(
    r"\b(\d{1,2}(:\d{2})?\s*(am|pm|a\.m\.|p\.m\.|o'?clock)|noon|midnight)\b",
    re.IGNORECASE,
)


def _normalize(text: Optional[str]) -> str:
    return re.sub(r"\s+", " ", (text or "")).strip().lower()


async def reject_unconfirmed_time(
    text: str, *, resident_id: Optional[str], conversation_session_id: Optional[str]
) -> Optional[str]:
    """None if `text` is safe to persist. Otherwise a short reason string
    explaining why it was rejected. Fails CLOSED: a time is claimed but
    there's no session/resident to verify it against -> reject."""
    match = _TIME_CLAIM_RE.search(text or "")
    if not match:
        return None
    claim = _normalize(match.group(0))
    q: dict = {"role": "user"}
    if conversation_session_id:
        q["session_id"] = conversation_session_id
    elif resident_id:
        q["resident_id"] = resident_id
    else:
        return "a specific time was included but there is no conversation on record to verify it against"
    async for turn in db.conversations.find(q, {"_id": 0, "text": 1}):
        if claim in _normalize(turn.get("text")):
            return None
    return f"a specific time ('{match.group(0).strip()}') was included but the resident never stated it this conversation"
