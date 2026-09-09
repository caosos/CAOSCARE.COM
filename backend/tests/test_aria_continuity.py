"""Layer B — cross-session continuity (routes/aria_continuity.py).

The "I thought I just told you" problem. A new session must begin with
useful continuity from recent prior sessions WITHOUT behaving as if an old
workflow is still running.

Covers the workability acceptance cases:
  1  fresh session, familiar person — continuity present, no forced topic
  2  "I thought I just told you" — the prior statement is recoverable
  3  workflow does not leak — no old task marked active
  4  relevant thread can return — an unfinished session is flagged
  5  irrelevant history stays out — old / other-resident sessions excluded
  6  current state overrides old words — Layer E is authoritative, pointed to
  7  provider portability — plain dict / plain str, no provider keys
  8  baseline is not an opener script — no "continue" / "what do you need"

Seeds db.conversations directly (the existing turn store) + a
realtime_diagnostics session_ended row; no HTTP needed for the logic.
"""
import asyncio
import os
import sys
import uuid
from datetime import timedelta, timezone

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _skip_if_down():
    try:
        import requests
        requests.get(os.environ.get("REACT_APP_BACKEND_URL", "http://127.0.0.1:8000")
                     + "/api/health", timeout=3).raise_for_status()
    except Exception:
        pytest.skip("backend / mongo not reachable")


async def _seed_turns(db, resident_id, session_id, turns, base_dt):
    docs = []
    for i, (role, content) in enumerate(turns):
        docs.append({
            "resident_id": resident_id, "session_id": session_id, "role": role,
            "content": content, "source": "realtime",
            "created_at": (base_dt + timedelta(seconds=i * 20)).isoformat(),
        })
    await db.conversations.insert_many(docs)


async def _run():
    from deps import db
    from models import now_utc
    from routes.aria_continuity import resolve_continuity, render_continuity_block

    rid = f"res_test_{uuid.uuid4().hex[:8]}"
    other = f"res_test_{uuid.uuid4().hex[:8]}"
    now = now_utc()

    recent_sid = f"rt_recent_{uuid.uuid4().hex[:6]}"
    old_sid = f"rt_old_{uuid.uuid4().hex[:6]}"
    dropped_sid = f"rt_drop_{uuid.uuid4().hex[:6]}"
    other_sid = f"rt_other_{uuid.uuid4().hex[:6]}"
    current_sid = f"rt_current_{uuid.uuid4().hex[:6]}"

    try:
        # ~40 min ago, ended cleanly (resident said goodbye).
        await _seed_turns(db, rid, recent_sid, [
            ("assistant", "Good afternoon, Helen. What's on your mind?"),
            ("user", "The reading light over my chair keeps flickering"),
            ("assistant", "I'm sorry, that sounds annoying. I've made a note of it."),
            ("user", "and turn the desk lamp down to about half"),
            ("assistant", "Done — the desk lamp is at fifty percent."),
            ("user", "that's all for now"),
            ("assistant", "Take care, Helen."),
        ], now - timedelta(minutes=42))
        await db.realtime_diagnostics.insert_one({
            "session_id": recent_sid, "event_type": "session_ended",
            "meta": {"reason": "resident_end_call"}, "created_at": (now - timedelta(minutes=40)).isoformat(),
        })

        # ~3 h ago, the call DROPPED (companion_timeout) mid-topic.
        await _seed_turns(db, rid, dropped_sid, [
            ("assistant", "Good afternoon, Helen. I'm here."),
            ("user", "I wanted to ask about the trip to the pharmacy on Thursday"),
            ("assistant", "Let me see what's available..."),
        ], now - timedelta(hours=3))
        await db.realtime_diagnostics.insert_one({
            "session_id": dropped_sid, "event_type": "session_ended",
            "meta": {"reason": "companion_timeout"}, "created_at": (now - timedelta(hours=3, minutes=-5)).isoformat(),
        })

        # 5 DAYS ago — outside the window, must not appear.
        await _seed_turns(db, rid, old_sid, [
            ("user", "Tell me about the garden club meeting"),
            ("assistant", "Of course..."),
        ], now - timedelta(days=5))

        # A DIFFERENT resident, right now — must not appear for `rid`.
        await _seed_turns(db, other, other_sid, [
            ("user", "My name is Arthur and I need my blanket"),
            ("assistant", "Okay, Arthur."),
        ], now - timedelta(minutes=10))

        # ---- CASE 1 / 5: fresh session; recent + dropped included, old + other out
        st = await resolve_continuity(rid, current_session_id=current_sid)
        assert st["has_continuity"] is True
        sids = {s["session_id"] for s in st["sessions"]}
        assert recent_sid in sids and dropped_sid in sids
        assert old_sid not in sids, "a 5-day-old session is not continuity"
        assert other_sid not in sids, "another resident's session must never leak in"

        block = render_continuity_block(st, "Helen")

        # ---- CASE 2: the prior substantive statement is recoverable verbatim
        assert "reading light over my chair keeps flickering" in block
        assert "desk lamp down to about half" in block

        # ---- CASE 4: the dropped session is flagged as possibly unfinished
        drop = next(s for s in st["sessions"] if s["session_id"] == dropped_sid)
        assert drop["unfinished"] is True
        clean = next(s for s in st["sessions"] if s["session_id"] == recent_sid)
        assert clean["unfinished"] is False
        assert "pick this back up" in block  # only for the dropped one

        # ---- CASE 3 / 8: it is context, not a workflow, and not an opener
        low = block.lower()
        assert "not an active request" in low
        for banned in ("what do you need", "would you like to continue",
                       "last time we were discussing", "shall we pick up",
                       "let's continue where we left off"):
            assert banned not in low, f"opener-script phrase leaked: {banned!r}"

        # ---- CASE 6: continuity points at Layer E as the authority on live status
        assert "authoritative current status" in block

        # ---- CASE 7: provider-portable — plain str / plain dict, no vendor keys
        assert isinstance(block, str)
        blob = repr(st).lower()
        for vendor in ("openai", "gpt", "claude", "anthropic", "assistant_id", "thread_id"):
            assert vendor not in blob

        # trivial-only turns don't count as continuity
        empty_sid = f"rt_empty_{uuid.uuid4().hex[:6]}"
        await _seed_turns(db, rid, empty_sid, [
            ("user", "hello"), ("assistant", "Hi Helen."), ("user", "mm"), ("user", "."),
        ], now - timedelta(minutes=5))
        st2 = await resolve_continuity(rid, current_session_id=current_sid)
        es = next((s for s in st2["sessions"] if s["session_id"] == empty_sid), None)
        # session is listed but renders to nothing substantive
        if es is not None:
            from routes.aria_continuity import _compact_turns
            assert _compact_turns(es["_rows"], "Helen") == []

    finally:
        await db.conversations.delete_many({"resident_id": {"$in": [rid, other]}})
        await db.realtime_diagnostics.delete_many(
            {"session_id": {"$in": [recent_sid, dropped_sid]}})


async def _economics():
    """Rendered block is hard-capped no matter how long the prior calls were."""
    from deps import db
    from models import now_utc
    from routes.aria_continuity import resolve_continuity, render_continuity_block, _TOTAL_CHAR_CAP

    rid = f"res_test_{uuid.uuid4().hex[:8]}"
    sid = f"rt_huge_{uuid.uuid4().hex[:6]}"
    now = now_utc()
    big = []
    for i in range(120):
        big.append(("user", f"This is a long substantive sentence number {i} about the weather and my knees and the garden."))
        big.append(("assistant", f"I hear you, that's point {i}, and here is a fairly wordy reply that goes on for a while to pad length."))
    try:
        await _seed_turns(db, rid, sid, big, now - timedelta(minutes=30))
        st = await resolve_continuity(rid, current_session_id="rt_x")
        block = render_continuity_block(st, "Helen")
        assert len(block) <= _TOTAL_CHAR_CAP + 600, len(block)
        # and it kept the TAIL (a follow-up refers to the end of the call)
        assert "number 119" in block or "number 118" in block
    finally:
        await db.conversations.delete_many({"resident_id": rid})


async def _empty():
    from routes.aria_continuity import resolve_continuity, render_continuity_block
    st = await resolve_continuity(f"res_none_{uuid.uuid4().hex[:8]}", "rt_x")
    assert st["has_continuity"] is False
    assert render_continuity_block(st, "Helen") == ""
    assert render_continuity_block(None, "Helen") == ""


def test_continuity_cases():
    _skip_if_down()
    asyncio.get_event_loop().run_until_complete(_run())


def test_continuity_economics_capped():
    _skip_if_down()
    asyncio.get_event_loop().run_until_complete(_economics())


def test_continuity_empty_is_pure_baseline():
    _skip_if_down()
    asyncio.get_event_loop().run_until_complete(_empty())
