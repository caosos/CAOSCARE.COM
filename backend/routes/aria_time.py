"""Shared conversational time phrasing for the Aria context layers.

One source of truth for "how long ago" wording so Layer E (operational
state) and Layer B (continuity) describe the same instant the same way.
Never read a raw timestamp aloud - these produce the phrase a person uses.
"""
from datetime import datetime, timezone

from models import now_utc


def parse_dt(v):
    if v is None:
        raise ValueError("no timestamp")
    dt = v if hasattr(v, "isoformat") and not isinstance(v, str) else \
        datetime.fromisoformat(str(v).replace("Z", "+00:00"))
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def age_phrase(when) -> str:
    """Coarse, conversational age of `when` (datetime or ISO string)."""
    try:
        secs = (now_utc() - parse_dt(when)).total_seconds()
    except Exception:
        return "at an unknown time"
    if secs < 90:
        return "just now"
    if secs < 3600:
        return f"about {max(1, round(secs / 60))} minutes ago"
    if secs < 6 * 3600:
        return f"about {round(secs / 3600)} hours ago"
    if secs < 24 * 3600:
        return "earlier today"
    if secs < 48 * 3600:
        return "yesterday"
    return f"{round(secs / 86400)} days ago"
