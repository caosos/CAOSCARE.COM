"""Lifelong resident memory (Michael, 2026-10-12: "she shouldn't forget what happened 3 days ago ...
residents keep this Aria for life; every conversation carries on"). Each finished conversation is
summarized once into the existing memories store (events bin, category "conversation", source_session),
and folded into ONE bounded life story per resident (facts bin, category "life_story", pinned).
The model call is stubbed; scratch DB only."""
import asyncio
import json
import os
import sys
import uuid
from datetime import timedelta

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if os.environ.get("DB_NAME") in ("caoscare", "", None):
    pytest.skip("writes resident/memory rows; scratch DB only", allow_module_level=True)

from deps import db  # noqa: E402
from models import now_utc  # noqa: E402
import routes.aria_life_memory as life  # noqa: E402

CALLS = []


async def fake_chat(system, user):
    CALLS.append((system, user))
    if "life story" in system.lower():
        return "Michael lives in Room 214. His granddaughter Lily had a piano recital. He follows the Cubs."
    if "Lily" in user:
        return json.dumps({"summary": "Michael said his granddaughter Lily has a piano recital tomorrow.", "substantive": True})
    if "Cubs" in user:
        return json.dumps({"summary": "Michael asked how the Cubs did; Aria did not have the score.", "substantive": True})
    return json.dumps({"summary": "", "substantive": False})


async def _scenario(monkeypatch):
    monkeypatch.setattr(life, "_chat", fake_chat)
    CALLS.clear()
    rid = f"res_lm_{uuid.uuid4().hex[:6]}"

    async def seed(sid, ago, turns, trusted=True):
        t0 = now_utc() - ago
        await db.conversations.insert_many([
            {"resident_id": rid, "session_id": sid, "role": r, "content": c, "trusted": (trusted if r == "user" else None),
             "created_at": (t0 + timedelta(seconds=5 * i)).isoformat()} for i, (r, c) in enumerate(turns)])
    try:
        await seed("rt_old", timedelta(days=30), [("assistant", "Hey, Michael."), ("user", "My granddaughter Lily has a piano recital tomorrow."), ("assistant", "How exciting!")])
        await seed("rt_mid", timedelta(days=4), [("assistant", "Yes, Michael?"), ("user", "How did the Cubs do?"), ("assistant", "I don't have the score.")])
        await seed("rt_noise", timedelta(days=2), [("assistant", "Hi."), ("user", "Jeg heter.")])
        await seed("rt_untrusted", timedelta(days=1), [("user", "My son Bob is visiting.")], trusted=False)
        await seed("rt_live", timedelta(seconds=30), [("user", "Hey Aria, what's up?")])   # still going / just ended

        n = await life.summarize_pending_sessions(rid, current_session_id="rt_now", max_sessions=10)
        ev = await db.memories.find({"resident_id": rid, "category": "conversation"}).sort("event_at", 1).to_list(20)
        shown = [e for e in ev if not e.get("archived")]
        assert [e["source_session"] for e in shown] == ["rt_old", "rt_mid"], [e["source_session"] for e in ev]
        assert {e["source_session"] for e in ev} == {"rt_old", "rt_mid", "rt_noise", "rt_untrusted"}   # recorded as done, hidden
        assert all(e["bin"] == "events" for e in ev) and "Lily" in shown[0]["text"]
        assert not any("Bob" in u for _, u in CALLS), "an untrusted turn reached the summarizer"
        assert n == 4
        story = await db.memories.find_one({"resident_id": rid, "category": "life_story"})
        assert story and story["pinned"] and story["bin"] == "facts" and "Lily" in story["text"]
        assert len(story["text"]) <= life.LIFE_STORY_MAX_CHARS
        assert set(story["covers_sessions"]) >= {"rt_old", "rt_mid"}

        CALLS.clear()
        assert await life.summarize_pending_sessions(rid, current_session_id="rt_now") == 0   # idempotent
        assert CALLS == []
        assert await db.memories.count_documents({"resident_id": rid, "category": "life_story"}) == 1

        # it reaches the prompt: life story under its own heading, the episodes as dated moments
        from routes.realtime_companion_memory import build_resident_profile_and_memory
        block = await build_resident_profile_and_memory(rid, {"name": "Michael Test"}, "Michael", "Michael Test")
        assert "Your story with Michael so far" in block and "piano recital" in block
        assert "asked how the Cubs did" in block
    finally:
        await db.conversations.delete_many({"resident_id": rid})
        await db.memories.delete_many({"resident_id": rid})


def test_conversations_become_lifelong_memory(monkeypatch):
    asyncio.get_event_loop().run_until_complete(_scenario(monkeypatch))
