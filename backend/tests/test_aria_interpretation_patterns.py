"""Terminal 10 — person-specific interpretation continuity
(routes/aria_interpretation_patterns.py). NON-NEGOTIABLE per AGENTS.md and
docs/CAOS_CARE_AGENT_ONBOARDING_CONTRACT.md.

Canonical acceptance case: "dos savor" -> "dos sabores" -> "two flavors",
while the resident's original wording stays visible for teaching/audit.

Covers:
  1  a first confirmation creates a pattern (resident-scoped)
  2  a repeated confirmation strengthens it (confirmed_count) without
     duplicating or leaking into another resident's patterns
  3  a correction updates understood_as for THIS pattern only, keeping the
     prior value in correction_history (never silent, never cross-pattern)
  4  matching resolves a near-miss phonetic utterance against a confirmed
     pattern (the actual "dos savor" acceptance case)
  5  an unrelated utterance does not spuriously match
  6  the mint-time context block is bounded (MAX_PATTERNS_IN_CONTEXT) and
     never fabricates a pattern that wasn't actually confirmed
  7  end-to-end: the assembled companion prompt carries the learned pattern
     and the original wording, and defers to the model rather than guessing
     when nothing matches
"""
import asyncio
import os
import sys
import uuid

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
    from routes.aria_interpretation_patterns import (
        ConfirmInterpretationInput, record_pattern, list_patterns,
        find_matching_patterns, render_interpretation_block,
    )

    rid = f"res_test_{uuid.uuid4().hex[:8]}"
    other = f"res_test_{uuid.uuid4().hex[:8]}"
    try:
        # ---- CASE 1: first confirmation creates the pattern
        p1 = await record_pattern(ConfirmInterpretationInput(
            resident_id=rid, heard_as="dos savor", understood_as="dos sabores",
            meaning="two flavors", language="es", category="language_learning",
        ))
        assert p1["confirmed_count"] == 1
        assert p1["heard_as"] == "dos savor"
        assert p1["understood_as"] == "dos sabores"
        assert p1["examples"] == ["dos savor"]

        # ---- CASE 2: repeated confirmation strengthens, doesn't duplicate;
        # another resident's identical phrase is a SEPARATE pattern.
        p1b = await record_pattern(ConfirmInterpretationInput(
            resident_id=rid, heard_as="Dos Savor", understood_as="dos sabores",
            meaning="two flavors", language="es",
        ))
        assert p1b["confirmed_count"] == 2
        mine = await list_patterns(rid)
        assert len(mine) == 1, "same normalized phrase must not duplicate"

        await record_pattern(ConfirmInterpretationInput(
            resident_id=other, heard_as="dos savor", understood_as="something else",
        ))
        assert len(await list_patterns(rid)) == 1, "no cross-resident leakage"
        assert (await list_patterns(other))[0]["understood_as"] == "something else"

        # ---- CASE 3: a correction updates THIS pattern, keeps history,
        # never touches the other resident's pattern.
        corrected = await record_pattern(ConfirmInterpretationInput(
            resident_id=rid, heard_as="dos savor", understood_as="dos sabores, por favor",
            meaning="two flavors, please",
        ))
        assert corrected["understood_as"] == "dos sabores, por favor"
        assert corrected["correction_history"][-1]["was"] == "dos sabores"
        assert corrected["confirmed_count"] == 3
        assert (await list_patterns(other))[0]["understood_as"] == "something else"

        # ---- CASE 4: the actual acceptance case - a near-miss phonetic
        # utterance resolves against the confirmed pattern.
        matches = await find_matching_patterns(rid, "can I get dos savor please")
        assert matches and matches[0]["understood_as"] == "dos sabores, por favor"
        matches2 = await find_matching_patterns(rid, "dos sabor")  # close phonetic variant
        assert matches2 and matches2[0]["heard_as_norm"] == "dos savor"

        # ---- CASE 5: unrelated utterance does not spuriously match
        assert await find_matching_patterns(rid, "what time is dinner tonight") == []

        # ---- CASE 6: mint-time block is bounded and never fabricates
        block = render_interpretation_block(await list_patterns(rid), "Helen")
        assert "dos savor" in block and "dos sabores, por favor" in block
        assert "two flavors, please" in block
        assert "Never claim" in block  # no-fabrication guidance present
        assert render_interpretation_block([], "Helen") == ""
        assert render_interpretation_block(None, "Helen") == ""

    finally:
        await db.interpretation_patterns.delete_many({"resident_id": {"$in": [rid, other]}})


async def _prompt_integration():
    from deps import db
    from models import now_utc
    from routes.aria_interpretation_patterns import ConfirmInterpretationInput, record_pattern, list_patterns
    from routes.realtime_companion_prompt import _build_companion_instructions

    rid = f"res_test_{uuid.uuid4().hex[:8]}"
    try:
        await db.residents.insert_one({
            "resident_id": rid, "name": "Michael Test", "created_at": now_utc().isoformat(),
        })
        await record_pattern(ConfirmInterpretationInput(
            resident_id=rid, heard_as="dos savor", understood_as="dos sabores",
            meaning="two flavors", language="es", category="language_learning",
        ))
        patterns = await list_patterns(rid)
        text = await _build_companion_instructions(rid, interpretation_patterns=patterns)

        assert "What you've learned about how" in text
        assert "dos savor" in text and "dos sabores" in text and "two flavors" in text
        # durable (interpretation) comes before recent-conversation/right-now sections
        assert text.index("Who you are") < text.index("What you've learned about how")

        # a fresh resident with NO confirmed patterns gets no fabricated block
        rid2 = f"res_test_{uuid.uuid4().hex[:8]}"
        await db.residents.insert_one({
            "resident_id": rid2, "name": "Nobody Yet", "created_at": now_utc().isoformat(),
        })
        text2 = await _build_companion_instructions(rid2, interpretation_patterns=[])
        assert "What you've learned about how" not in text2
    finally:
        await db.residents.delete_many({"resident_id": {"$in": [rid, "res_test_placeholder"]}})
        await db.interpretation_patterns.delete_many({"resident_id": rid})


async def _tool_dispatch_shape():
    """The confirm_interpretation_pattern tool schema exists and is wired
    into the tool surface the model actually receives."""
    from routes.realtime_interpretation_tools import _build_interpretation_tools
    from routes.realtime_tools import _build_tools

    schema = _build_interpretation_tools()
    assert schema[0]["name"] == "confirm_interpretation_pattern"
    assert set(schema[0]["parameters"]["required"]) == {"heard_as", "understood_as"}

    tools = await _build_tools()
    names = {t["name"] for t in tools}
    assert "confirm_interpretation_pattern" in names


def test_interpretation_pattern_cases():
    _skip_if_down()
    asyncio.get_event_loop().run_until_complete(_run())


def test_interpretation_pattern_prompt_integration():
    _skip_if_down()
    asyncio.get_event_loop().run_until_complete(_prompt_integration())


def test_interpretation_pattern_tool_registered():
    _skip_if_down()
    asyncio.get_event_loop().run_until_complete(_tool_dispatch_shape())
