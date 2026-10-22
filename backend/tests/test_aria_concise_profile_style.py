"""concise_natural replaces the persona's style sections; supportive_guided keeps them word for word.

Owner directive 2026-10-21 after Room 214 rt_d3ahe1bf: "I don't really need enthusiasm, I just need you to
be normal." The one-paragraph profile lost to the shared persona ("warm, brighter, storyteller, ask if they
want to hear more"), so the profile now selects those sections instead of overriding them from the end.
"""
import asyncio
import os
import sys
import uuid

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from deps import db  # noqa: E402
from aria_guidance_profiles import CONCISE_STYLE, companion_style  # noqa: E402
from routes.realtime_companion_prompt import _build_companion_instructions  # noqa: E402

run = asyncio.get_event_loop().run_until_complete
SUPPORTIVE_MARKERS = ("a calm, warm, deeply present companion", "Brighter if they want company",
                      "Storyteller mode is part of your job", "Then ask if they want to hear more",
                      "keep talking, ask about their day")


@pytest.fixture()
def residents():
    ids = {p: f"res_style_{p or 'default'}_{uuid.uuid4().hex[:6]}" for p in (None, "supportive_guided", "concise_natural")}
    for p, rid in ids.items():
        run(db.residents.insert_one({"resident_id": rid, "name": "Rose Test", "preferred_name": "Rose", "room": "T-STY",
                                     **({"aria_guidance_profile": p} if p else {})}))
    yield ids
    run(db.residents.delete_many({"resident_id": {"$in": list(ids.values())}}))


def test_supportive_residents_keep_the_persona_word_for_word(residents):
    for p in (None, "supportive_guided"):
        text = run(_build_companion_instructions(residents[p]))
        for m in SUPPORTIVE_MARKERS:
            assert m in text, (p, m)
        assert "easygoing, sharp and straightforward" not in text and "Sure you are." not in text
    assert companion_style(None) == {} and companion_style("supportive_guided") == {}


def test_concise_profile_replaces_the_eager_sections(residents):
    text = run(_build_companion_instructions(residents["concise_natural"]))
    for m in SUPPORTIVE_MARKERS:
        assert m not in text, m
    for section in CONCISE_STYLE.values():
        assert section in text
    for phrase in ("never bubbly, eager or upbeat", "are banter, not a request for a simpler explanation",
                   "don't apologize, thank them, explain, or promise to change", "Never thank them for feedback",
                   "'I'm eating a plum' -> 'Good time of year for them.'", "at most 'One sec.' once",
                   "247,392 is 'two hundred forty-seven thousand, three hundred ninety-two'"):
        assert phrase in text, phrase
    # Safety, truth and end-call rules are not style: still present.
    for kept in ("## Truth discipline", "call `call_for_help`", "call `end_call` IMMEDIATELY", "## Language"):
        assert kept in text, kept
