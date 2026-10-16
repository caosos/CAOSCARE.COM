"""Aria's opening line (Michael, 2026-10-12): after "Hey Aria" she answers the
way a person answers their name - one short line with the resident's name,
not the same long time-of-day greeting every call - and she does not open
the same way as her previous call. Pure render tests run anywhere; the
lookup test needs a scratch DB."""
import asyncio
import os
import sys
import uuid

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from routes.aria_opening import render_opening_block  # noqa: E402


def test_wake_word_opening_is_a_short_answer_to_their_name():
    b = render_opening_block({"wake": True, "last_opening": None}, "Michael")
    assert "Hey Aria" in b and "Michael" in b
    assert "one short line" in b and "good afternoon" not in b.lower()


def test_previous_openings_are_history_not_quoted_into_the_prompt():
    """aria-room-opening-context-regression-003: quoted at the end of the prompt, a prior opening was
    answered and repeated; rotation already keeps its lead out of the suggestions."""
    prior = "Good afternoon, Michael. I'm here with you."
    b = render_opening_block({"wake": True, "last_opening": prior, "recent_openings": [prior]}, "Michael")
    assert prior not in b and "most recent calls opened" not in b
    tap = render_opening_block({"wake": False, "last_opening": None}, "Michael")
    assert "Hey Aria" not in tap and "one short line" not in tap         # the normal greeting rules apply
    b = render_opening_block({"wake": False, "last_opening": "Hi Michael.", "recent_openings": ["Hi Michael."]}, "Michael")
    assert "Hey Aria" not in b and "Hi Michael." not in b


def test_opening_block_is_bounded():
    b = render_opening_block({"wake": True, "last_opening": "x" * 900, "recent_openings": ["x" * 900]}, "Michael")
    assert "x" * 20 not in b and len(b) < 1200


@pytest.mark.skipif(os.environ.get("DB_NAME") in ("caoscare", "", None), reason="writes conversation rows; scratch DB only")
def test_resolve_reads_the_previous_sessions_first_assistant_line():
    from deps import db
    from routes.aria_opening import resolve_opening
    rid = f"res_{uuid.uuid4().hex[:8]}"

    async def go():
        await db.conversations.insert_many([
            {"resident_id": rid, "session_id": "rt_a", "role": "assistant", "content": "Old first line.", "created_at": "2031-01-01T10:00:00+00:00"},
            {"resident_id": rid, "session_id": "rt_b", "role": "assistant", "content": "Good afternoon, Michael.", "created_at": "2031-01-01T11:00:00+00:00"},
            {"resident_id": rid, "session_id": "rt_b", "role": "user", "content": "Hi.", "created_at": "2031-01-01T11:00:03+00:00"},
            {"resident_id": rid, "session_id": "rt_b", "role": "assistant", "content": "Later line.", "created_at": "2031-01-01T11:00:05+00:00"},
        ])
        try:
            o = await resolve_opening(rid, "rt_new", "wake_word")
            assert (o["wake"], o["last_opening"]) == (True, "Good afternoon, Michael."), o
            o2 = await resolve_opening(rid, "rt_b", "manual_kiosk")   # a reconnect of rt_b does not quote itself
            assert (o2["wake"], o2["last_opening"]) == (False, "Old first line."), o2
            none = await resolve_opening(None, "rt_x", "wake_word")
            assert {k: none[k] for k in ("wake", "last_opening", "recent_openings", "minutes_since_last", "name")} == {
                "wake": True, "last_opening": None, "recent_openings": [], "minutes_since_last": None, "name": None}
        finally:
            await db.conversations.delete_many({"resident_id": rid})
    asyncio.get_event_loop().run_until_complete(go())


def test_wake_soon_after_a_call_carries_context_without_calling_out_recency():
    b = render_opening_block({"wake": True, "last_opening": "Hey, Michael.", "minutes_since_last": 4.3}, "Michael")
    assert "one short line" in b and "Carry prior context forward silently" in b
    assert "minute(s) ago" not in b and "Didn't I just talk to you" not in b and "back again" not in b.lower()
    far = render_opening_block({"wake": True, "last_opening": None, "minutes_since_last": 300}, "Michael")
    assert "minute(s) ago" not in far and "one short line" in far
