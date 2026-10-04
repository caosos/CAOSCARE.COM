"""Phase A (voice prompt reduction): the resident companion prompt describes
exactly the tools a channel provides, states each mandatory rule once, and
keeps identity, governance, emergency, provenance and session-ending rules.

Builds the real prompt; reads only the facility record (no writes, no model
call). See docs/reports/2026-10-04-voice-prompt-context-audit.md.
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from routes import companion_prompt_contract as contract  # noqa: E402
from routes.companion_tool_guidance import CAPABILITY  # noqa: E402
from routes.voice_bridge_tools import BRIDGE_TOOLS  # noqa: E402


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


def _universe() -> set:
    from routes.realtime_tools import _build_tools
    return {t["name"] for t in _run(_build_tools())}


def _prompt(tools=BRIDGE_TOOLS, channel="voice") -> str:
    from routes.realtime_companion_prompt import _build_companion_instructions
    return _run(_build_companion_instructions(None, tools=tools, channel=channel))


def _profile(tools=BRIDGE_TOOLS) -> str:
    from routes.realtime_companion_memory import build_resident_profile_and_memory
    r = {"name": "Margaret Hughes", "preferred_name": "Maggie", "low_vision": True}
    return _run(build_resident_profile_and_memory("res_phase_a_absent", r, "Maggie",
                                                  "Margaret Hughes", tools))


def test_every_tool_described_is_available():
    text = _prompt() + _profile()
    assert contract.unsupported_tool_claims(text, BRIDGE_TOOLS, _universe()) == []


def test_every_bridge_tool_is_represented():
    text = _prompt()
    universe = _universe()
    for name in BRIDGE_TOOLS:
        assert name in universe, f"{name} is not a real resident tool"
        assert CAPABILITY[name].lower() in text.lower(), f"{name} missing from the capability list"


def test_no_unsupported_capability_claimed():
    assert contract.unsupported_capability_claims(_prompt(), BRIDGE_TOOLS, "voice") == []
    universe = _universe()
    kiosk = _prompt(tools=None, channel="kiosk")
    assert contract.unsupported_capability_claims(kiosk, universe, "kiosk") == []
    assert contract.unsupported_tool_claims(kiosk, universe, universe) == []


def test_emergency_instructions_remain():
    for text in (_prompt(), _prompt(tools=None, channel="kiosk")):
        safety = text[text.index("## Safety"):]
        assert "chest pain" in safety and "`call_for_help`" in safety
        assert "severity='emergency'" in safety
        assert "Never make medical claims" in safety
        assert contract.rule_counts(text)["emergency"] == 1


def test_receipt_and_provenance_rules_remain():
    text = _prompt()
    for marker in ("## Truth discipline", "## Attribution discipline",
                   "unless you have actually invoked the tool",
                   "NEVER say you can do something and then fail"):
        assert marker in text, marker
    profile = _profile()
    assert "Provenance (TSB-001)" in profile and "it's on your file with us" in profile


def test_resident_and_community_identity_remain():
    from routes.realtime_facility import _facility_now
    text = _prompt()
    profile = _profile()
    assert "Maggie" in profile and "do not use it" in profile  # preferred name rule
    assert "Margaret Hughes" in profile
    now = _run(_facility_now())
    assert now["label"] in text[text.index("## Right now"):]
    assert "You are Aria" in text or "Your name is" in text


def test_deterministic_session_ending_remains():
    from routes.voice_bridge_session import ending_phrase
    text = _prompt()
    assert "`end_call` IMMEDIATELY" in text and "that'll be all for now" in text
    assert ending_phrase("That'll be all, Aria.") and ending_phrase("Goodbye, Aria.")


def test_no_duplicate_mandatory_instruction():
    for text in (_prompt(), _prompt(tools=None, channel="kiosk")):
        assert contract.duplicated_instructions(text) == []
        assert contract.missing_sections(text) == []


def test_kiosk_channel_keeps_its_tools_and_screen():
    text = _prompt(tools=None, channel="kiosk")
    for name in ("mark_resting", "update_preferred_name", "get_room_status", "end_call"):
        assert f"`{name}`" in text
    assert "## What's on the kiosk screen" in text


def test_static_text_precedes_per_call_text():
    text = _prompt()
    assert text.index("## Safety") < text.index("## Right now")


def test_help_wording_follows_actual_state():
    """Michael 2026-10-04: no "already on the way" for a request that was only
    created; acknowledged / assigned / en route each said only when true."""
    for text in (_prompt(), _prompt(tools=None, channel="kiosk")):
        assert contract.forbidden_statements(text) == []
        assert contract.rule_counts(text)["help_status"] == 1
        for phrase in ("I've requested help", "say it was acknowledged",
                       "say who it was assigned to",
                       "on the way only when you have been told staff are actually on their way"):
            assert phrase in text, phrase
        safety = text[text.index("## Safety"):]
        assert "help has been requested" in safety and "on the way" not in safety


def test_aria_is_not_described_as_living_in_the_wall():
    for text in (_prompt(), _prompt(tools=None, channel="kiosk")):
        who = text[text.index("## Who you are"):text.index("## How you sound")]
        assert "wall" not in who
        assert "through the voice device in their room" in who
        assert "You have known them for a long time" in who   # tone kept

