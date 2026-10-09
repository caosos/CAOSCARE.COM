"""RQ-045: research honesty. Live-web claims only with a live provider;
the endpoint reports `live`; prompt carries the truth invariants. httpx is
stubbed - no network, no provider calls."""
import asyncio
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from routes import research
from routes.realtime_truth_rules import research_tool_description, research_prompt_line, TRUTH_INVARIANTS
from routes.realtime_self_knowledge import _system_self_knowledge


def _set_live(monkeypatch, on):
    if on:
        monkeypatch.setenv("CAOSCARE_RESEARCH_PROVIDER", "openai_web_search")
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")
        monkeypatch.setenv("OPENAI_RESEARCH_MODEL", "test-model")
    else:
        monkeypatch.delenv("CAOSCARE_RESEARCH_PROVIDER", raising=False)


def test_text_without_live_provider(monkeypatch):
    _set_live(monkeypatch, False)
    d = research_tool_description()
    assert "NOT a live lookup" in d and "live web" not in d.replace("NOT a live lookup", "")
    assert "Never say you looked it up" in d
    p = research_prompt_line()
    assert "do NOT have internet access" in p and "look things up on the live web" not in p
    assert "NOT live" in _system_self_knowledge() or "do NOT have" in _system_self_knowledge()


def test_text_with_live_provider(monkeypatch):
    _set_live(monkeypatch, True)
    assert "live web" in research_tool_description()
    assert "look things up on the live web" in research_prompt_line()


def test_invariants_present():
    assert "get_weather" in TRUTH_INVARIANTS and "same turn" in TRUTH_INVARIANTS
    assert "request_staff_help" in TRUTH_INVARIANTS and "returned ok" in TRUTH_INVARIANTS
    assert "playing music" in TRUTH_INVARIANTS


def test_built_tool_schema_follows_provider(monkeypatch):
    from routes.realtime_tools import _build_tools
    _set_live(monkeypatch, False)
    tools = asyncio.run(_build_tools())
    d = next(t for t in tools if t["name"] == "research_topic")["description"]
    assert "NOT a live lookup" in d
    _set_live(monkeypatch, True)
    d = next(t for t in asyncio.run(_build_tools()) if t["name"] == "research_topic")["description"]
    assert "live web" in d and "NOT a live lookup" not in d


class _Resp:
    def __init__(self, data): self._d = data
    status_code = 200
    def raise_for_status(self): pass
    def json(self): return self._d


class _Client:
    def __init__(self, *a, **k): pass
    async def __aenter__(self): return self
    async def __aexit__(self, *a): return False
    async def post(self, url, json=None, headers=None):
        return _Resp({"choices": [{"message": {"content": "an answer"}}]})


def test_endpoint_not_live_without_provider(monkeypatch):
    monkeypatch.setattr(research.httpx, "AsyncClient", _Client)

    async def _noop(**k): return {}
    monkeypatch.setattr(research, "log_event", _noop)
    _set_live(monkeypatch, False)
    monkeypatch.setattr(research, "OPENAI_API_KEY", "k")
    out = asyncio.run(research.research_topic("who won"))
    assert out.source == "openai" and out.live is False and out.citations == []


def test_prompt_assembly_includes_invariants(monkeypatch):
    from routes.realtime_companion_prompt import _build_companion_instructions
    _set_live(monkeypatch, False)
    text = asyncio.run(_build_companion_instructions(None))
    assert "Say only what a tool result proves" in text
    assert "do NOT have internet access" in text
    assert "mark_resting" in text and "end_call" in text
