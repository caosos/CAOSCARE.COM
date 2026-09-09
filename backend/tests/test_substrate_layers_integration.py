"""Layer B (continuity) + Layer E (operational state) assembled together in
the resident companion prompt — the Room 214 shape.

CASE 6 (current state overrides old words): the recent conversation says a
call is unanswered; Layer E says it was resolved. The assembled prompt must
carry BOTH — the history for meaning, the resolved status as the authority —
and must not re-assert the call as still pending.

Also asserts block ORDER: durable baseline → continuity → "right now".
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


async def _run():
    from deps import db
    from models import now_utc
    from routes.aria_continuity import resolve_continuity
    from routes.aria_operational_state import resolve_operational_state
    from routes.realtime_companion_prompt import _build_companion_instructions

    rid = f"res_test_{uuid.uuid4().hex[:8]}"
    room = f"itest_{uuid.uuid4().hex[:6]}"
    now = now_utc()
    prior_sid = f"rt_prior_{uuid.uuid4().hex[:6]}"
    alert_id = f"alert_{uuid.uuid4().hex[:12]}"

    try:
        await db.residents.insert_one({
            "resident_id": rid, "name": "Helen Torres", "room": room,
            "created_at": now.isoformat(),
        })
        # ~1h ago: she pressed for the bathroom; the recap will contain that.
        await db.conversations.insert_many([
            {"resident_id": rid, "session_id": prior_sid, "role": "user",
             "content": "I need help getting to the bathroom and nobody has come",
             "source": "realtime", "created_at": (now - timedelta(hours=1)).isoformat()},
            {"resident_id": rid, "session_id": prior_sid, "role": "assistant",
             "content": "I've let the nursing staff know, Helen. I'll stay with you.",
             "source": "realtime", "created_at": (now - timedelta(hours=1, seconds=-20)).isoformat()},
        ])
        await db.realtime_diagnostics.insert_one({
            "session_id": prior_sid, "event_type": "session_ended",
            "meta": {"reason": "companion_timeout"},
            "created_at": (now - timedelta(minutes=55)).isoformat(),
        })
        # Layer E truth NOW: that event is RESOLVED (staff came).
        await db.alerts.insert_one({
            "alert_id": alert_id, "resident_id": rid, "room": room,
            "status": "resolved", "severity": "assist", "triggered_by": "rf_pendant",
            "message": "RF pendant pressed", "resident_stated_reason": "needs the bathroom",
            "press_count": 3, "presses": [], "aria_state": "dismissed",
            "created_at": (now - timedelta(hours=1, minutes=5)).isoformat(),
            "acknowledged_at": (now - timedelta(minutes=50)).isoformat(),
            "acknowledged_by": "N. Osei", "resolved_at": (now - timedelta(minutes=45)).isoformat(),
            "resolved_by": "N. Osei",
        })

        continuity = await resolve_continuity(rid, current_session_id="rt_new")
        op_state = await resolve_operational_state(rid, room, alert_id=None)
        text = await _build_companion_instructions(
            rid, operational_state=op_state, continuity=continuity,
        )

        # history is preserved for meaning
        assert "nobody has come" in text
        # current authority is present and says resolved / handled
        assert "What's actually happening right now" in text
        assert "resolved" in text.lower()
        assert "N. Osei" in text
        # the resolved item is framed as history, not as waiting work
        assert "do not chase these" in text.lower()
        # continuity explicitly defers to the "right now" section
        assert "authoritative current status" in text
        # ORDER: persona → continuity(recap) → operational(right now).
        # Match section headers, not the phrase inside continuity prose.
        i_persona = text.index("## Who you are")
        i_recap = text.index("## Where you and Helen were")
        i_now = text.index("## What's actually happening right now")
        assert i_persona < i_recap < i_now

    finally:
        await db.residents.delete_many({"resident_id": rid})
        await db.conversations.delete_many({"resident_id": rid})
        await db.alerts.delete_many({"resident_id": rid})
        await db.realtime_diagnostics.delete_many({"session_id": prior_sid})


async def _run_bce_order():
    """B + C + E all present in one assembled prompt, in the conceptual
    order: persona/baseline → cross-session recap (B) → this-call state (C)
    → authoritative right-now state (E)."""
    from deps import db
    from models import now_utc
    from routes.aria_continuity import resolve_continuity
    from routes.aria_conversation_state import resolve_conversation_state
    from routes.aria_operational_state import resolve_operational_state
    from routes.realtime_companion_prompt import _build_companion_instructions

    rid = f"res_test_{uuid.uuid4().hex[:8]}"
    room = f"bce_{uuid.uuid4().hex[:6]}"
    now = now_utc()
    prior_sid = f"rt_prior_{uuid.uuid4().hex[:6]}"
    cur_sid = f"rt_cur_{uuid.uuid4().hex[:6]}"
    task_id = f"task_{uuid.uuid4().hex[:8]}"
    try:
        await db.residents.insert_one({
            "resident_id": rid, "name": "Helen Torres", "room": room,
            "created_at": now.isoformat(),
        })
        # B: a prior session ~40 min ago
        await db.conversations.insert_many([
            {"resident_id": rid, "session_id": prior_sid, "role": "user",
             "content": "the reading light keeps flickering", "source": "realtime",
             "created_at": (now - timedelta(minutes=40)).isoformat()},
            {"resident_id": rid, "session_id": prior_sid, "role": "assistant",
             "content": "I've noted that, Helen.", "source": "realtime",
             "created_at": (now - timedelta(minutes=39)).isoformat()},
        ])
        await db.realtime_diagnostics.insert_one({
            "session_id": prior_sid, "event_type": "session_ended",
            "meta": {"reason": "resident_end_call"},
            "created_at": (now - timedelta(minutes=38)).isoformat()})
        # C + E: a request filed in THIS call, still open
        await db.conversations.insert_many([
            {"resident_id": rid, "session_id": cur_sid, "role": "user",
             "content": "it's freezing, get someone", "source": "realtime",
             "created_at": (now - timedelta(minutes=2)).isoformat()},
            {"resident_id": rid, "session_id": cur_sid, "role": "assistant",
             "content": "I've let the staff know.", "source": "realtime",
             "created_at": (now - timedelta(minutes=2, seconds=-20)).isoformat()},
        ])
        await db.staff_tasks.insert_one({
            "task_id": task_id, "title": "Check room heat", "status": "pending",
            "category": "maintenance", "source": "aria_voice",
            "resident_id": rid, "room": room, "resident_words": "it's freezing",
            "conversation_session_id": cur_sid,
            "created_at": (now - timedelta(minutes=2)).isoformat()})

        continuity = await resolve_continuity(rid, current_session_id=cur_sid)
        conv_state = await resolve_conversation_state(rid, cur_sid)
        op_state = await resolve_operational_state(rid, room)
        text = await _build_companion_instructions(
            rid, operational_state=op_state, continuity=continuity,
            conversation_state=conv_state,
        )

        # match section headers ('## ...'), not the same phrase where it
        # appears inside the continuity block's prose.
        i_persona = text.index("## Who you are")
        i_recap = text.index("## Where you and Helen were")
        i_call = text.index("## This call so far")
        i_now = text.index("## What's actually happening right now")
        assert i_persona < i_recap < i_call < i_now, (i_persona, i_recap, i_call, i_now)
        # C and E agree the task is still open (E lists it -> no downgrade)
        assert "in motion" in text
    finally:
        await db.residents.delete_many({"resident_id": rid})
        await db.conversations.delete_many({"resident_id": rid})
        await db.staff_tasks.delete_many({"task_id": task_id})
        await db.realtime_diagnostics.delete_many({"session_id": prior_sid})


def test_layers_b_and_e_current_state_wins():
    _skip_if_down()
    asyncio.get_event_loop().run_until_complete(_run())


def test_layers_bce_assemble_in_order():
    _skip_if_down()
    asyncio.get_event_loop().run_until_complete(_run_bce_order())
