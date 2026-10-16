"""Consecutive calls do not open with the same line (aria-room-conversation-cleanup-002).

Scratch Room 214, 2026-10-16 09:26-09:27Z: three tap calls in a row
(rt_10s3ng43_1792142773769, rt_uvqmiwa5_1792142815409, rt_9h57dbcg_1792142856903)
all opened "I'm here, Michael." The previous opening WAS in the prompt, but the
prompt also suggested "I'm here" twice (night greeting note, help-button line)
and only said "vary your words" against it. The opening block now offers short
natural openings minus any whose lead a recent call used.
"""
import asyncio
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from routes.aria_opening import (TAP_OPENINGS, WAKE_OPENINGS, opening_lead, render_opening_block,  # noqa: E402
                                 resolve_opening, suggested_openings)
from routes.realtime_companion_prompt import _build_companion_instructions  # noqa: E402
from routes.realtime_facility import greeting_note  # noqa: E402

run = asyncio.get_event_loop().run_until_complete
REAL_REPEAT = "I'm here, Michael.\n\nIf you want a little company, tell me what's on your mind."


def test_lead_ignores_the_name_and_what_follows():
    assert opening_lead(REAL_REPEAT, "Michael") == "i'm here"
    assert opening_lead("I’m here, Michael. If you're just taking a moment", "Michael") == "i'm here"
    assert opening_lead("Hey there, Michael.", "Michael") == "hey there" != opening_lead("Hey, Michael.", "Michael")


def test_the_scratch_repeat_is_not_suggested_again():
    o = {"wake": False, "recent_openings": [REAL_REPEAT]}
    sug = suggested_openings(o, "Michael", "night")
    assert sug and all(not s.startswith("I'm here") for s in sug)
    block = render_opening_block(o, "Michael", "night")
    assert "Start differently from every one of these" in block and "I'm here, Michael." in block  # quoted, not offered
    assert "Good night" not in block                                      # an opening "good night" reads as goodbye


def test_time_of_day_greeting_is_one_option_not_a_script():
    assert "Good evening, Michael." in suggested_openings({"wake": False}, "Michael", "evening")
    assert not any("Good" in s for s in suggested_openings({"wake": True}, "Michael", "evening"))   # wake: no time greeting


def test_prompt_no_longer_hardcodes_i_m_here():
    assert "I'm here" not in greeting_note("night") and "good night" in greeting_note("night")
    text = run(_build_companion_instructions(None, opening={"wake": False, "recent_openings": []}))
    assert "a quiet 'I'm here' is enough" not in text and "try 'I'm here'" not in text
    assert "follow 'How this call opens' below" in text
    assert text.rstrip().endswith("never narrate what you are about to do.")   # the opening rule still closes it


@pytest.fixture()
def resident():
    from deps import db
    rid = f"res_open_{uuid.uuid4().hex[:8]}"
    yield rid, db
    run(db.conversations.delete_many({"resident_id": rid}))


@pytest.mark.parametrize("wake", [False, True])
def test_consecutive_calls_rotate_through_real_resolve_and_render(resident, wake):
    """Six calls in a row; each 'says' the first line it was offered, as the model did."""
    rid, db = resident
    t0 = datetime.now(timezone.utc) - timedelta(hours=1)
    said = []
    for i in range(6):
        sid = f"rt_open_{i}_{rid}"
        o = run(resolve_opening(rid, sid, "wake_word" if wake else "manual_kiosk"))
        offered = suggested_openings(o, "Michael", "night")
        assert offered, f"call {i}: nothing to offer"
        line = offered[0]
        recent_leads = {opening_lead(t, "Michael") for t in said[-3:]}
        assert opening_lead(line, "Michael") not in recent_leads, (i, line, said[-3:])
        block = render_opening_block(o, "Michael", "night")
        for prev in said[-3:]:
            assert f'"{prev}"' in block                                   # the last three are quoted
        said.append(line)
        run(db.conversations.insert_many([
            {"resident_id": rid, "session_id": sid, "role": "assistant", "content": line,
             "created_at": (t0 + timedelta(minutes=i)).isoformat()},
            {"resident_id": rid, "session_id": sid, "role": "user", "content": "Goodbye.",
             "created_at": (t0 + timedelta(minutes=i, seconds=5)).isoformat()}]))
    assert all(said[i] != said[i + 1] for i in range(len(said) - 1))
    assert len(set(said[:4])) == 4                                        # four calls, four different openings
    assert set(said) <= {o.format(n="Michael") for o in (WAKE_OPENINGS if wake else TAP_OPENINGS)}


def test_three_real_repeats_leave_natural_options(resident):
    rid, db = resident
    t0 = datetime.now(timezone.utc) - timedelta(minutes=10)
    for i, sid in enumerate(["rt_10s3ng43", "rt_uvqmiwa5", "rt_9h57dbcg"]):
        run(db.conversations.insert_one({"resident_id": rid, "session_id": f"{sid}_{rid}", "role": "assistant",
                                         "content": REAL_REPEAT, "created_at": (t0 + timedelta(minutes=i)).isoformat()}))
    o = run(resolve_opening(rid, "rt_next", "manual_kiosk"))
    assert len(o["recent_openings"]) == 3 and o["last_opening"].startswith("I'm here, Michael.")
    assert suggested_openings(o, "Michael", "night") == ["Hi, Michael.", "There you are, Michael.", "Hey there, Michael."]
