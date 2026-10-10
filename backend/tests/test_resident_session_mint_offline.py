"""Test-reality gap 5: the real POST /api/realtime/session resident mint runs offline.

The gate skips the old iter10/iter11 mint tests without an OpenAI key, so nothing offline
proved the mint body, the instruction invariants, the tool set or the turn_detection config.
OpenAI is replaced by a recorder (no network). A golden check, not provider acceptance:
real acceptance of the schema needs one owner-approved live call.
"""
import asyncio
import os
import sys
import types

import httpx
import pytest
from fastapi import FastAPI

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if os.environ.get("DB_NAME") in ("caoscare", "", None):
    pytest.skip("touches the database; point DB_NAME at a scratch database", allow_module_level=True)

from routes import realtime as realtime_routes  # noqa: E402
from routes import realtime_resident_session  # noqa: E402
from routes.realtime_audio_config import DEFAULT_NOISE_REDUCTION, DEFAULT_VAD  # noqa: E402
from routes.realtime_tools import _build_tools  # noqa: E402
from routes.realtime_truth_rules import TRUTH_INVARIANTS  # noqa: E402

REAL = httpx.AsyncClient
CALLS = []


class Recorder:
    def __init__(self, *a, **k): pass
    async def __aenter__(self): return self
    async def __aexit__(self, *e): return False

    async def post(self, url, headers=None, json=None, **kw):
        CALLS.append({"url": url, "json": json, "headers": headers})

        class R:
            status_code = 200
            text = "{}"
            @staticmethod
            def json(): return {"value": "ek_fake", "expires_at": 0}
        return R()


def run(c):
    return asyncio.get_event_loop().run_until_complete(c)


@pytest.fixture
def mint(monkeypatch):
    fake = types.SimpleNamespace(AsyncClient=Recorder)
    monkeypatch.setattr(realtime_routes, "httpx", fake)
    monkeypatch.setattr(realtime_resident_session, "httpx", fake)
    monkeypatch.setattr(realtime_resident_session, "_require_openai_key", lambda: "sk-test-not-real")
    CALLS.clear()
    app = FastAPI(); app.include_router(realtime_routes.router, prefix="/api")

    async def go():
        async with REAL(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
            return await c.post("/api/realtime/session", json={"resident_id": "res_offline_mint_none"})
    return run(go())


def test_mint_body_sent_to_openai_is_the_expected_shape(mint):
    assert mint.status_code == 200
    (call,) = CALLS
    assert call["url"].endswith("/realtime/client_secrets")
    assert call["headers"]["Authorization"] == "Bearer sk-test-not-real"
    sess = call["json"]["session"]
    assert sess["type"] == "realtime" and sess["model"] and sess["audio"]["output"]["voice"]
    assert set(sess) == {"type", "model", "instructions", "audio"}  # tools/turn_detection are applied by the client, not at mint


def test_instructions_carry_the_truth_and_end_call_invariants(mint):
    ins = CALLS[0]["json"]["session"]["instructions"]
    assert ins == mint.json()["_caos"]["instructions"]
    assert TRUTH_INVARIANTS.strip()[:60] in ins
    assert "end_call" in ins and "FIRST" in ins


def test_client_config_returned_with_tools_vad_and_noise_reduction(mint):
    caos = mint.json()["_caos"]
    expected = [t["name"] for t in run(_build_tools())]
    assert [t["name"] for t in caos["tools"]] == expected and len(expected) >= 25
    for must in ("end_call", "request_staff_help", "call_for_help", "toggle_light", "research_topic"):
        assert must in expected
    assert caos["turn_detection"] == DEFAULT_VAD and caos["turn_detection"]["create_response"] is True
    assert caos["turn_detection"]["interrupt_response"] is True
    assert caos["noise_reduction"] == DEFAULT_NOISE_REDUCTION == {"type": "far_field"}
    assert caos["tool_choice"] == "auto"
