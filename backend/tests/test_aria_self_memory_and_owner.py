"""Resident Aria knows the resident from memory, says limits once, and only
the verified owner room hears who the creator is (aria-room-runtime-fixes-001).

Fixtures mirror the real Room 214 memory shapes (db.memories: a pinned
life_story, durable facts, conversation summaries in the events bin, some
archived "(nothing substantive said)"). DB-direct through deps.db.
"""
import asyncio
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from deps import db  # noqa: E402
from routes.realtime_memory_recall import usual_asks, render_usual_asks  # noqa: E402
from routes.realtime_companion_prompt import _build_companion_instructions  # noqa: E402
from routes.owner_room_context import owner_room_block, owner_room_prompt  # noqa: E402

run = asyncio.get_event_loop().run_until_complete

SUMMARIES = [
    "Michael asked Aria to turn on the overhead light and thanked her afterwards.",
    "Michael asked Aria to turn off the desk lamp, and that was all for now.",
    "Michael asked Aria to dim the overhead light to fifty percent.",
    "Michael asked Aria for today's news, and they discussed international topics.",
    "Michael asked Aria about the world news, and then they discussed elections in general.",
    "Michael asked Aria to turn the TV back up.",
    "Michael asked Aria if she could hear him and mentioned his TV being off.",
    "Michael asked Aria about supper, and she sent a request to the kitchen.",
    "Michael asked Aria about her capabilities regarding her own code.",
    "Michael asked Aria how she remembers their conversations.",
]


def test_usual_asks_counts_real_topics_only():
    asks = dict(usual_asks(SUMMARIES))
    assert asks["turning the lights or lamps on, off, or dimmer"] == 3
    assert asks["news and current events"] == 2
    assert asks["the TV - power, volume, sound"] == 2
    assert asks["how you work and what you can do"] == 2
    assert "the weather" not in asks and "meals and the menu" not in asks   # once is not "usually"
    assert render_usual_asks("Michael", []) == ""


@pytest.fixture()
def resident():
    rid = f"res_mem_{uuid.uuid4().hex[:8]}"
    now = datetime.now(timezone.utc)
    run(db.residents.insert_one({"resident_id": rid, "name": "Michael Test", "preferred_name": "Michael",
                                 "room": "T-MEM", "memory": "Test identity. Not a care resident."}))
    docs = [{"memory_id": f"mem_life_{rid}", "resident_id": rid, "bin": "facts", "category": "life_story", "pinned": True,
             "importance": 5, "archived": False,
             "text": "Michael prefers warm lighting for his desk lamp and worked as a maintenance technician at Brookdale."},
            {"memory_id": f"m1_{rid}", "resident_id": rid, "bin": "facts", "category": "history", "pinned": True,
             "importance": 5, "archived": False, "text": "Michael Chambers is the human creator and owner of CAOSCARE."},
            {"memory_id": f"m2_{rid}", "resident_id": rid, "bin": "events", "category": "conversation", "archived": True,
             "event_at": now.isoformat(), "text": "(nothing substantive said)"}]
    for i, s in enumerate(SUMMARIES):
        docs.append({"memory_id": f"c{i}_{rid}", "resident_id": rid, "bin": "events", "category": "conversation",
                     "archived": False, "event_at": (now - timedelta(hours=i + 1)).isoformat(), "text": s})
    run(db.memories.insert_many(docs))
    yield rid
    run(db.memories.delete_many({"resident_id": rid}))
    run(db.residents.delete_one({"resident_id": rid}))


def test_prompt_carries_memory_usual_asks_and_the_rules(resident):
    text = run(_build_companion_instructions(resident))
    assert "## Your story with Michael so far" in text and "warm lighting for his desk lamp" in text
    assert "creator and owner of CAOSCARE" in text                          # durable fact is there
    assert "## What Michael usually asks you for" in text
    assert "turning the lights or lamps on, off, or dimmer (came up in 3 of your last 10 conversations)" in text
    assert "(nothing substantive said)" not in text                          # archived junk stays out
    assert "## When they ask about themselves" in text
    assert "three to five concrete, specific examples" in text
    assert "never answer with a generic description of their personality" in text.lower()
    assert "## Say a limitation once" in text
    assert "you can't send emails or open tickets" in text
    assert "`check_medication_status`" in text and "Never say someone is coming" in text
    assert "never tell them to look at a screen" in text.lower()
    assert "I'll let the team know you asked" not in text                   # old over-promise removed
    assert "confirm a caregiver is on the way" not in text
    # The owner block is NOT part of the shared resident prompt.
    assert "Who you are talking to (verified owner test room)" not in text


def test_owner_block_text_and_scope():
    block = owner_room_block("Michael Chambers", "Michael")
    assert "Michael is Michael Chambers, the person who created and owns CAOS Care" in block
    assert "'Well, Michael, that would be you - so yes, we should probably fix that.'" in block
    assert "Never speak of the creator or the developers as someone else here" in block
    assert "cannot send email or open tickets" in block and "Never mention any of this outside this room" in block


def test_owner_style_block_is_in_the_owner_room_block_only(resident):
    # Owner directive 2026-10-21 (Room 214 session rt_y6k2od0z): answer what was asked, no offers/menus,
    # let an unfinished thought finish, "stop"/"chill" -> one or two words, follow his change of topic,
    # silence is fine, a goodbye to dot/ChatGPT or a quoted one is not for Aria.
    block = owner_room_block("Michael Chambers", "Michael")
    for phrase in ("## How to talk with Michael (this room only)", "Match the detail to the task",
                   "No closing offers or menus", "'Mm?' or 'Go on', then wait",
                   "you have already been cut off", "including a change of topic",
                   "reply with one or two words ('Sure.') or nothing - never explain how you'll change",
                   "Silence is fine", "One reply per turn", "said to someone else (dot, ChatGPT",
                   "don't call `end_call`", "never claim you do", "Safety, truth, tool and end-call rules still apply"):
        assert phrase in block, phrase
    assert block.index("Who you are talking to") < block.index("How to talk with Michael")
    # Every other resident's prompt is unchanged: no owner style block without the verified Room 214 mint.
    assert "How to talk with" not in run(_build_companion_instructions(resident))


def test_owner_block_needs_the_verified_room_214_mint():
    # No lease / a claimed room=214 with no backend lease never proves the owner room.
    assert run(owner_room_prompt({"room": "214", "resident_id": "res_x", "kiosk_id": "kio_x"}, None)) == ""
    assert run(owner_room_prompt({"room": "215", "resident_id": "res_x"}, {"claimed": True, "session_id": "s"})) == ""


def test_owner_goodbye_line_and_scope(resident):
    # Owner 2026-10-21: "she needs to say goodnight or goodbye" - owner room only.
    from routes.owner_room_context import owner_goodbye_line
    tz = "America/Chicago"
    at = lambda h: datetime(2026, 10, 21, h, 30, tzinfo=ZoneInfo(tz))
    assert [owner_goodbye_line(tz, at(h)) for h in (4, 5, 12, 19, 20, 23)] == [
        "Goodnight.", "Goodbye.", "Goodbye.", "Goodbye.", "Goodnight.", "Goodnight."]
    block = owner_room_block("Michael Chambers", "Michael", "Goodnight.")
    assert 'your goodbye is exactly "Goodnight."' in block
    assert "your goodbye is exactly" not in owner_room_block("Michael Chambers", "Michael")
    assert "your goodbye is exactly" not in run(_build_companion_instructions(resident))


def test_owner_style_block_has_the_builder_rule_and_examples():
    block = owner_room_block("Michael Chambers", "Michael")
    for phrase in ("Michael is building you", "Never say you can't or won't become something",
                   "No lead-ins", "say it in your greeting only", "Examples from real calls in this room",
                   "RIGHT - stop after the answer."):
        assert phrase in block, phrase


def test_owner_wake_opens_with_a_clear_hello():
    # Owner 2026-10-21: "when she wakes say hello or hi or something so I know she's there".
    from routes.aria_opening import suggested_openings, greeting_line, WAKE_OPENINGS
    owner = {"wake": True, "owner_room": True, "name": "Michael", "recent_openings": []}
    assert suggested_openings(owner, "Michael") == ["Hi, Michael.", "Hello, Michael.", "Hey, Michael."]
    assert greeting_line({**owner, "recent_openings": ["Hi, Michael.", "Hello, Michael.", "Hey, Michael."]}) == "Hi, Michael."
    other = {"wake": True, "name": "Rose", "recent_openings": []}
    assert suggested_openings(other, "Rose") == [o.format(n="Rose") for o in WAKE_OPENINGS][:3]   # unchanged
