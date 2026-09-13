"""Terminal 10 — conversation-parity turn-taking instrumentation
(routes/aria_turn_taking.py). Proves the metrics are correctly DERIVED from
the realtime_diagnostics events useRealtimeVoice.js already writes - no new
capture, no raw transcript text read.

Covers:
  1  ordinary turn: silence-before-response gap and response duration
  2  a genuine barge-in (assistant_speaking=True) is counted
  3  a barge-in immediately after response_created is flagged "premature"
  4  a long silence gap is flagged
  5  an empty/unknown session returns zero counts, not an error
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


async def _seed(db, sid, events, base_dt):
    docs = []
    for i, (event_type, offset_ms, assistant_speaking) in enumerate(events):
        docs.append({
            "session_id": sid, "event_type": event_type,
            "assistant_speaking": assistant_speaking,
            "created_at": (base_dt + timedelta(milliseconds=offset_ms)).isoformat(),
        })
    await db.realtime_diagnostics.insert_many(docs)


async def _run():
    from deps import db
    from models import now_utc
    from routes.aria_turn_taking import resolve_turn_taking

    now = now_utc()
    sid = f"rt_tt_{uuid.uuid4().hex[:6]}"
    try:
        await _seed(db, sid, [
            # ordinary turn: resident speaks, 1200ms gap, Aria replies for 900ms
            ("speech_started", 0, False),
            ("speech_stopped", 800, False),
            ("response_created", 2000, None),      # 1200ms gap
            ("response_done", 2900, None),          # 900ms response
        ], now)

        # second, cleaner scenario in its own session: premature interrupt + long gap
        sid2 = f"rt_tt_{uuid.uuid4().hex[:6]}"
        await _seed(db, sid2, [
            ("speech_started", 0, False),
            ("speech_stopped", 500, False),
            ("response_created", 6000, None),        # 5500ms gap -> long
            ("speech_started", 6300, True),           # barge-in 300ms after response_created -> premature
            ("response_done", 9000, None),
        ], now)

        r1 = await resolve_turn_taking(sid)
        assert r1["user_turn_count"] >= 1
        assert r1["assistant_turn_count"] >= 1
        assert r1["avg_silence_before_response_ms"] is not None
        assert 1100 <= r1["avg_silence_before_response_ms"] <= 1300
        assert r1["avg_response_duration_ms"] is not None
        assert 800 <= r1["avg_response_duration_ms"] <= 1000

        r2 = await resolve_turn_taking(sid2)
        assert r2["barge_in_count"] == 1
        assert r2["premature_interrupt_count"] == 1
        assert r2["long_gap_count"] == 1
        assert r2["max_silence_before_response_ms"] >= 4000

        # ---- CASE 5: unknown session -> zero counts, not an error
        empty = await resolve_turn_taking(f"rt_none_{uuid.uuid4().hex[:6]}")
        assert empty["user_turn_count"] == 0
        assert empty["barge_in_count"] == 0
        assert empty["avg_silence_before_response_ms"] is None

    finally:
        await db.realtime_diagnostics.delete_many({"session_id": {"$in": [sid, sid2]}})


def test_turn_taking_metrics():
    _skip_if_down()
    asyncio.get_event_loop().run_until_complete(_run())
