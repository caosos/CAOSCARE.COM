"""Access guard and rate limit for the public POST /research endpoint (RQ-049).

Only active when a paid live provider is configured (provider != none): then a
caller must hold a live Aria room session (resident_id + session_id, same
check as /memory/realtime-turn) or present a valid owner token (the owner
/aria build has no resident). Calls are rate limited per room (owner: per
user, no session: per IP) in memory, CAOSCARE_RESEARCH_RATE_PER_MIN (default 6).
Every denial records a research_lookup event with status failed.
"""
import os
import time
from collections import defaultdict, deque
from typing import Optional

from fastapi import HTTPException, Request

from routes.events import log_event
from routes.session_grounding import find_live_session
from routes import research_openai_search as oas

WINDOW_SECONDS = 60.0
_hits: dict = defaultdict(deque)


def rate_limit_per_min() -> int:
    try:
        return max(1, int(os.environ.get("CAOSCARE_RESEARCH_RATE_PER_MIN", "6")))
    except ValueError:
        return 6


def reset_rate_limit() -> None:
    _hits.clear()


def _allow(key: str) -> bool:
    now = time.monotonic()
    q = _hits[key]
    while q and now - q[0] > WINDOW_SECONDS:
        q.popleft()
    if len(q) >= rate_limit_per_min():
        return False
    q.append(now)
    return True


async def _owner(request: Request) -> Optional[dict]:
    from deps import get_current_user
    try:
        u = await get_current_user(request)
    except HTTPException:
        return None
    return u if u.get("role") == "owner" else None


async def _deny(status: int, reason: str, detail: str, context: Optional[dict] = None):
    context = context or {}
    await log_event(event_type="research_lookup", source="resident_aria", target_type="tool",
                    action="research_topic", status="failed", error_code=str(status),
                    error_message=reason, metadata={"provider": oas.provider_name(), "denied": True, "live": False},
                    resident_id=context.get("resident_id"), room=context.get("room"),
                    conversation_id=context.get("conversation_id"), actor_id=context.get("actor_id"),
                    actor_role=context.get("actor_role"))
    raise HTTPException(status_code=status, detail=detail)


async def enforce(request: Request, resident_id: Optional[str], session_id: Optional[str]) -> dict:
    """Return verified caller context; raise 403/429 for an invalid paid call."""
    if oas.provider_name() != oas.SOURCE:
        return {}
    ip = request.client.host if request.client else "unknown"
    key = None
    owner = await _owner(request)
    if owner:
        key = f"owner:{owner.get('user_id')}"
        context = {"actor_id": owner.get("user_id"), "actor_role": owner.get("role")}
    else:
        found = await find_live_session(resident_id or "", session_id or "")
        if not found:
            await _deny(403, "no live session", "Research is only available during a live conversation.")
        key = f"room:{found.get('room') or ip}"
        context = {"resident_id": resident_id, "room": found.get("room"),
                   "conversation_id": session_id}
    if not _allow(key):
        await _deny(429, "rate limit", "I can't look that up right now - too many lookups. Please try again in a minute.", context)
    return context
