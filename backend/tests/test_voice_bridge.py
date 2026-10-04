"""Voice bridge spike: credential, session id and tool-schema checks.

The end-to-end turn (OpenAI + real services) is exercised against a running
backend in the spike's receipt (docs/PROJECT_STATE.md, 2026-10-03); these
are the offline guarantees.
"""
import asyncio

import pytest
from fastapi import HTTPException

from routes.voice_bridge import _check_token, _session_id
from routes.voice_bridge_tools import BRIDGE_TOOLS, bridge_tool_schemas


def test_bridge_refuses_when_not_configured(monkeypatch):
    monkeypatch.delenv("CAOSCARE_VOICE_BRIDGE_TOKEN", raising=False)
    with pytest.raises(HTTPException) as e:
        _check_token("Bearer anything")
    assert e.value.status_code == 503


def test_bridge_requires_matching_credential(monkeypatch):
    monkeypatch.setenv("CAOSCARE_VOICE_BRIDGE_TOKEN", "s3cret-token")
    for bad in (None, "", "Bearer wrong", "s3cret"):
        with pytest.raises(HTTPException) as e:
            _check_token(bad)
        assert e.value.status_code == 401
    _check_token("Bearer s3cret-token")  # no exception


def test_session_id_is_namespaced_and_sanitised():
    assert _session_id("abc-123") == "vb_abc-123"
    assert _session_id("a/b?c$d") == "vb_abcd"
    assert _session_id(None).startswith("vb_") and len(_session_id(None)) > 3


def test_bridge_tools_come_from_the_realtime_schemas():
    schemas = asyncio.run(bridge_tool_schemas())
    names = {s["function"]["name"] for s in schemas}
    assert names == set(BRIDGE_TOOLS)
    assert all(s["type"] == "function" and "parameters" in s["function"] for s in schemas)
