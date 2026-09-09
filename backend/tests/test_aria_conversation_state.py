"""Layer C — runtime conversation-vs-intent state (routes/aria_conversation_state.py).

Answers "has THIS call already filed or finished a request, or asked a
routing question awaiting an answer" — keyed by session_id, not resident_id,
so a reconnect that reuses the same session_id sees what this call already
did instead of treating the session's mere existence as license to start or
restart a task.

Covers:
  1  brand-new session (no turns, no tasks) -> None, empty block
  2  ordinary back-and-forth, no action -> conversation_active, empty block
  3  an open staff_task tied to this session -> action_in_progress
  4  a resolved staff_task, conversation just closing out -> action_completed
  5  a resolved staff_task, conversation has clearly moved on -> conversation_resumed
  6  last turn is an unanswered assistant question -> awaiting_required_detail
  7  provider portability - plain dict, no vendor keys
"""
import asyncio
import os
import sys
import uuid
from datetime import timedelta

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
    from routes.aria_conversation_state import resolve_conversation_state, render_conversation_state_block

    rid = f"res_test_{uuid.uuid4().hex[:8]}"
    now = now_utc()

    fresh_sid = f"rt_fresh_{uuid.uuid4().hex[:6]}"
    plain_sid = f"rt_plain_{uuid.uuid4().hex[:6]}"
    open_sid = f"rt_open_{uuid.uuid4().hex[:6]}"
    closing_sid = f"rt_closing_{uuid.uuid4().hex[:6]}"
    resumed_sid = f"rt_resumed_{uuid.uuid4().hex[:6]}"
    question_sid = f"rt_question_{uuid.uuid4().hex[:6]}"
    task_ids = []

    try:
        # ---- CASE 1: brand-new session, nothing persisted yet
        cs = await resolve_conversation_state(rid, fresh_sid)
        assert cs is None
        assert render_conversation_state_block(cs) == ""

        # ---- CASE 2: ordinary conversation, no action this session
        await _seed_turns(db, rid, plain_sid, [
            ("assistant", "Good afternoon."),
            ("user", "I couldn't sleep last night."),
            ("assistant", "I'm sorry to hear that."),
        ], now - timedelta(minutes=5))
        cs = await resolve_conversation_state(rid, plain_sid)
        assert cs["state"] == "conversation_active"
        assert render_conversation_state_block(cs) == ""

        # ---- CASE 3: an open request filed THIS session
        await _seed_turns(db, rid, open_sid, [
            ("user", "It's freezing in here, can someone check the heat"),
            ("assistant", "I've let the staff know."),
        ], now - timedelta(minutes=3))
        task_id = f"task_{uuid.uuid4().hex[:8]}"
        task_ids.append(task_id)
        await db.staff_tasks.insert_one({
            "task_id": task_id, "title": "Check room heat", "status": "pending",
            "resident_id": rid, "resident_words": "it's freezing in here",
            "conversation_session_id": open_sid,
            "created_at": (now - timedelta(minutes=3)).isoformat(),
        })
        cs = await resolve_conversation_state(rid, open_sid)
        assert cs["state"] == "action_in_progress"
        block = render_conversation_state_block(cs)
        assert "already have a request in motion" in block
        assert "do not file a second one" in block

        # ---- CASE 4: resolved this session, conversation is closing out
        completed_at = now - timedelta(minutes=8)
        await _seed_turns(db, rid, closing_sid, [
            ("user", "Can you turn the heat up two degrees"),
            ("assistant", "Done — I've bumped it up two degrees."),
        ], now - timedelta(minutes=9))
        task_id2 = f"task_{uuid.uuid4().hex[:8]}"
        task_ids.append(task_id2)
        await db.staff_tasks.insert_one({
            "task_id": task_id2, "title": "Adjust room heat", "status": "completed",
            "resident_id": rid, "resident_words": "turn the heat up two degrees",
            "conversation_session_id": closing_sid,
            "completed_by_name": "HVAC controller",
            "created_at": (now - timedelta(minutes=9)).isoformat(),
            "completed_at": completed_at.isoformat(),
        })
        await _seed_turns(db, rid, closing_sid, [
            ("user", "thank you"),
        ], completed_at + timedelta(seconds=5))
        cs = await resolve_conversation_state(rid, closing_sid)
        assert cs["state"] == "action_completed"
        block = render_conversation_state_block(cs)
        assert "already handled this in the same call" in block
        assert "do not restart the request" in block

        # ---- CASE 5: resolved earlier, conversation has clearly moved on
        task_id3 = f"task_{uuid.uuid4().hex[:8]}"
        task_ids.append(task_id3)
        await _seed_turns(db, rid, resumed_sid, [
            ("user", "Can you turn the heat up two degrees"),
            ("assistant", "Done — I've bumped it up two degrees."),
        ], now - timedelta(minutes=20))
        await db.staff_tasks.insert_one({
            "task_id": task_id3, "title": "Adjust room heat", "status": "completed",
            "resident_id": rid, "resident_words": "turn the heat up two degrees",
            "conversation_session_id": resumed_sid,
            "created_at": (now - timedelta(minutes=20)).isoformat(),
            "completed_at": (now - timedelta(minutes=19)).isoformat(),
        })
        await _seed_turns(db, rid, resumed_sid, [
            ("assistant", "Anything else on your mind?"),
            ("user", "Actually, tell me about the garden club."),
            ("assistant", "Of course..."),
            ("user", "That sounds lovely, thank you."),
        ], now - timedelta(minutes=15))
        cs = await resolve_conversation_state(rid, resumed_sid)
        assert cs["state"] == "conversation_resumed"
        block = render_conversation_state_block(cs)
        assert "that is done" in block.lower()

        # ---- CASE 6: last turn is an unanswered assistant question
        await _seed_turns(db, rid, question_sid, [
            ("user", "I need to talk to a nurse"),
            ("assistant", "Is this about medication or something else?"),
        ], now - timedelta(seconds=30))
        cs = await resolve_conversation_state(rid, question_sid)
        assert cs["state"] == "awaiting_required_detail"
        block = render_conversation_state_block(cs)
        assert "do not ask it again" in block.lower()

        # ---- CASE 7: provider-portable - plain dict, no vendor keys
        assert isinstance(cs, dict)
        blob = repr(cs).lower()
        for vendor in ("openai", "gpt", "claude", "anthropic", "assistant_id", "thread_id"):
            assert vendor not in blob

    finally:
        await db.conversations.delete_many({"resident_id": rid})
        await db.staff_tasks.delete_many({"task_id": {"$in": task_ids}})


async def _prompt_integration():
    from deps import db
    from models import now_utc
    from routes.aria_conversation_state import resolve_conversation_state
    from routes.realtime_companion_prompt import _build_companion_instructions

    rid = f"res_test_{uuid.uuid4().hex[:8]}"
    sid = f"rt_prompt_{uuid.uuid4().hex[:6]}"
    now = now_utc()
    task_id = f"task_{uuid.uuid4().hex[:8]}"

    try:
        await db.residents.insert_one({
            "resident_id": rid, "name": "Arthur Lowe", "created_at": now.isoformat(),
        })
        await _seed_turns(db, rid, sid, [
            ("user", "Can someone check my thermostat, it's freezing"),
            ("assistant", "I've let the staff know."),
        ], now - timedelta(minutes=2))
        await db.staff_tasks.insert_one({
            "task_id": task_id, "title": "Check thermostat", "status": "pending",
            "resident_id": rid, "resident_words": "it's freezing",
            "conversation_session_id": sid,
            "created_at": (now - timedelta(minutes=2)).isoformat(),
        })

        cs = await resolve_conversation_state(rid, sid)
        text = await _build_companion_instructions(rid, conversation_state=cs)

        assert "This call so far" in text
        assert "already have a request in motion" in text
        # placed after persona, before nothing-open op block (which is absent)
        assert text.index("Who you are") < text.index("This call so far")
    finally:
        await db.residents.delete_many({"resident_id": rid})
        await db.conversations.delete_many({"resident_id": rid})
        await db.staff_tasks.delete_many({"task_id": task_id})


def test_conversation_state_cases():
    _skip_if_down()
    asyncio.get_event_loop().run_until_complete(_run())


def test_conversation_state_renders_in_full_prompt():
    _skip_if_down()
    asyncio.get_event_loop().run_until_complete(_prompt_integration())
