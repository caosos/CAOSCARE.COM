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
    # Owner directives 2026-10-21 (Room 214 rt_y6k2od0z, rt_2l3ty0zy, rt_d3ahe1bf): what ONLY the owner room
    # adds; the general adult-to-adult style lives in the concise_natural profile (aria_guidance_profiles.py).
    block = owner_room_block("Michael Chambers", "Michael")
    for phrase in ("## Talking with Michael (this room only)", "'Mm?' or 'Go on', then wait",
                   "you have already been cut off", "including a change of topic", "never claim you do",
                   "said to someone else (dot, ChatGPT", "don't call `end_call`"):
        assert phrase in block, phrase
    assert block.index("Who you are talking to") < block.index("Talking with Michael")
    # Every other resident's prompt is unchanged: no owner style block without the verified Room 214 mint.
    assert "Talking with" not in run(_build_companion_instructions(resident))


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


def test_owner_style_block_has_the_builder_rule_and_the_real_examples():
    block = owner_room_block("Michael Chambers", "Michael")
    for phrase in ("Michael is building you", "Never say you can't or won't become something",
                   "Examples from real calls in this room",
                   "'That was simple, I was being sarcastic.'", "RIGHT - You: 'Yeah, I walked into that one.'",
                   "'I don't really need enthusiasm, I just need you to be normal.'", "RIGHT - You: 'Fair.'",
                   "'Well, this plum's pretty good.'"):
        assert phrase in block, phrase


def test_owner_wake_opens_with_a_clear_hello():
    # Owner 2026-10-21: "when she wakes say hello or hi or something so I know she's there".
    from routes.aria_opening import suggested_openings, greeting_line, WAKE_OPENINGS
    owner = {"wake": True, "owner_room": True, "name": "Michael", "recent_openings": []}
    assert suggested_openings(owner, "Michael") == ["Hi, Michael.", "Hello, Michael.", "Hey, Michael."]
    assert greeting_line({**owner, "recent_openings": ["Hi, Michael.", "Hello, Michael.", "Hey, Michael."]}) == "Hi, Michael."
    other = {"wake": True, "name": "Rose", "recent_openings": []}
    assert suggested_openings(other, "Rose") == [o.format(n="Rose") for o in WAKE_OPENINGS][:3]   # unchanged


def test_weather_next_days_line():
    # Room 214 rt_d3ahe1bf: "the rest of the week" needs more than today's data in ONE get_weather call.
    from routes.weather import _next_days
    daily = {"time": ["2026-10-21", "2026-10-22", "2026-10-23"], "temperature_2m_max": [26.7, 28.0, 29.0],
             "temperature_2m_min": [7.2, 9.0, 10.0], "precipitation_probability_max": [0, 10, 40], "weather_code": [0, 0, 61]}
    line = _next_days(daily)
    assert line.startswith(" Then Thursday: a high of 82 and a low of 48")
    assert "Friday: a high of 84 and a low of 50" in line and "40 percent chance of rain" in line
    assert _next_days({"time": ["2026-10-21"], "temperature_2m_max": [26.7], "temperature_2m_min": [7.2]}) == ""
