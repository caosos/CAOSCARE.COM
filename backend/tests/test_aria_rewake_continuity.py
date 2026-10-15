"""da-a3817b6b9c (Michael, 2026-10-12): a new "Hey Aria" should feel like continuing the conversation.
Builds the REAL resident prompt (_build_companion_instructions with the same continuity/opening inputs
_mint uses) for (1) an immediate re-wake one minute after a call and (2) a next-day wake 20 hours later,
from seeded conversation rows. Scratch DB only."""
import asyncio
import os
import sys
import uuid
from datetime import timedelta

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if os.environ.get("DB_NAME") in ("caoscare", "", None):
    pytest.skip("writes resident/conversation rows; scratch DB only", allow_module_level=True)

from deps import db  # noqa: E402
from models import now_utc  # noqa: E402
from routes.aria_continuity import resolve_continuity  # noqa: E402
from routes.aria_opening import resolve_opening  # noqa: E402
from routes.realtime_companion_prompt import _build_companion_instructions  # noqa: E402


async def _prompt(rid, sid):
    cont = await resolve_continuity(rid, sid, "214")
    opening = await resolve_opening(rid, sid, "wake_word")
    return await _build_companion_instructions(rid, continuity=cont, opening=opening)


async def _scenario(monkeypatch):
    monkeypatch.setenv("CAOSCARE_CONTINUITY_RECENT_MINUTES", "10")
    rid = f"res_rw_{uuid.uuid4().hex[:6]}"
    await db.residents.insert_one({"resident_id": rid, "name": "Michael Test", "preferred_name": "Michael"})
    try:
        async def seed(sid, ago, turns):
            t0 = now_utc() - ago
            await db.conversations.insert_many([
                {"resident_id": rid, "session_id": sid, "role": r, "content": c,
                 "created_at": (t0 + timedelta(seconds=5 * i)).isoformat()} for i, (r, c) in enumerate(turns)])

        await seed("rt_prev", timedelta(minutes=1), [
            ("assistant", "Good afternoon, Michael. I'm here with you."),
            ("user", "I'm just testing this out, I want to see how the Cubs did."),
            ("assistant", "I don't have the score with me right now.")])
        p = await _prompt(rid, "rt_rewake")
        assert "same conversation picking back up" in p and "Carry the thread forward silently" in p
        assert "I want to see how the Cubs did" in p                       # the last exchange is there
        assert "Didn't I just talk to you, Michael?" not in p and "Good afternoon, Michael. I'm here with you." in p
        assert "back again" not in p.lower() and "sit quietly" not in p.lower()
        assert "follow 'How this call opens' below" in p and "greet appropriately" not in p

        await db.conversations.delete_many({"resident_id": rid})
        # yesterday at 9 PM facility time, as seen the next afternoon
        from zoneinfo import ZoneInfo
        from routes.realtime_facility import FACILITY_TZ
        local_now = now_utc().astimezone(ZoneInfo(FACILITY_TZ))
        yday_9pm = (local_now - timedelta(days=1)).replace(hour=21, minute=0, second=0, microsecond=0)
        if local_now - yday_9pm < timedelta(hours=7):   # just after midnight 9 PM reads "about N hours ago":
            yday_9pm = yday_9pm.replace(hour=6)         # use yesterday morning so the run never depends on the clock
        await seed("rt_yday", now_utc() - yday_9pm, [
            ("assistant", "Hey, Michael."), ("user", "My granddaughter Lily has a recital tomorrow.")])
        p2 = await _prompt(rid, "rt_nextday")
        assert "### Yesterday" in p2 and "granddaughter Lily has a recital" in p2
        assert "same conversation picking back up" not in p2              # a new day is not the same conversation
        assert "never anything that is not written below" in p2
    finally:
        await db.conversations.delete_many({"resident_id": rid})
        await db.residents.delete_one({"resident_id": rid})


def test_rewake_and_next_day_prompts(monkeypatch):
    asyncio.get_event_loop().run_until_complete(_scenario(monkeypatch))
