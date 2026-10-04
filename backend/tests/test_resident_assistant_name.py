"""The resident-facing assistant name comes from one backend setting.

Default stays "Aria"; a test environment can set
CAOSCARE_RESIDENT_ASSISTANT_NAME (e.g. "Jarvis") and then the resident prompt
contains only that name.
"""
import asyncio

from routes.realtime_companion_prompt import _build_companion_instructions
from routes.realtime_self_knowledge import _system_self_knowledge
from routes.resident_assistant_identity import assistant_name


def test_default_name_is_aria(monkeypatch):
    monkeypatch.delenv("CAOSCARE_RESIDENT_ASSISTANT_NAME", raising=False)
    assert assistant_name() == "Aria"
    assert "Your name is Aria" in _system_self_knowledge()


def test_invalid_name_falls_back(monkeypatch):
    monkeypatch.setenv("CAOSCARE_RESIDENT_ASSISTANT_NAME", "<script>")
    assert assistant_name() == "Aria"


def test_configured_name_replaces_aria_in_resident_prompt(monkeypatch):
    monkeypatch.setenv("CAOSCARE_RESIDENT_ASSISTANT_NAME", "Jarvis")
    text = asyncio.run(_build_companion_instructions(None))
    assert "Your name is Jarvis" in text and "I'm Jarvis" in text
    assert "Aria" not in text
