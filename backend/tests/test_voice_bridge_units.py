"""Voice bridge pure-function checks: closing phrases, speakable text, and
the Home Assistant agent's HTTP client (timeouts, errors, unknown device).
The HA client is exercised with a stand-in HTTP session; no HA, no network."""
import asyncio
import importlib.util
from pathlib import Path

from routes.voice_bridge import speakable
from routes.voice_bridge_session import ending_phrase

_CLIENT = (Path(__file__).resolve().parents[2] / "integrations" / "home_assistant" /
           "custom_components" / "caoscare_conversation" / "bridge_client.py")
_spec = importlib.util.spec_from_file_location("bridge_client", _CLIENT)
bridge_client = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bridge_client)


def test_required_closing_phrases_end_the_session():
    for p in ["That'll be all.", "That'll be all, Aria.", "Goodbye, Aria.", "I'm done.",
              "Thank you, goodbye.", "that will be all", "Bye.", "I am done, thanks"]:
        assert ending_phrase(p), p


def test_other_speech_does_not_end_the_session():
    for p in ["I'm done eating, can you take my tray?", "Goodbye to my old room was hard",
              "That'll be all the help I need with the TV, now the lights", "Aria", "",
              "What's for dinner?", "I need help, I'm done for"]:
        assert not ending_phrase(p), p


def test_reply_is_plain_speakable_text():
    """TTS-unavailable case: the reply is plain text HA can show/log as-is."""
    assert speakable("**Dinner** is _roast chicken_.\n- see https://x.y") == "Dinner is roast chicken. see"
    assert speakable("") == ""


class _Resp:
    def __init__(self, status, body=None, delay=0, bad_json=False):
        self.status, self.body, self.delay, self.bad_json = status, body, delay, bad_json

    async def __aenter__(self):
        await asyncio.sleep(self.delay)
        return self

    async def __aexit__(self, *a):
        return False

    async def json(self):
        if self.bad_json:
            raise ValueError("not json")
        return self.body


class _Session:
    def __init__(self, resp):
        self.resp, self.calls = resp, []

    def post(self, url, json=None, headers=None):
        self.calls.append((url, json, headers))
        return self.resp


def _call(resp, timeout=1.0):
    payload = bridge_client.build_payload("What's for dinner?", "c1", "en", device_id="dev1")
    s = _Session(resp)
    return asyncio.run(bridge_client.call_bridge(s, "http://h/api/voice-bridge/turn", "tok", payload,
                                                 timeout=timeout)), s


def test_ha_client_success_passes_continuity_through():
    out, s = _call(_Resp(200, {"response_text": "Roast chicken.", "conversation_id": "c1",
                               "continue_conversation": True}))
    assert out == {"speech": "Roast chicken.", "conversation_id": "c1", "continue_conversation": True,
                   "ok": True, "error": None}
    url, body, headers = s.calls[0]
    assert body["device_id"] == "dev1" and headers["Authorization"] == "Bearer tok"


def test_ha_client_session_end_returns_to_wake_mode():
    out, _ = _call(_Resp(200, {"response_text": "Goodbye.", "conversation_id": "c1",
                               "continue_conversation": False}))
    assert out["continue_conversation"] is False and out["ok"]


def test_ha_client_timeout_speaks_fallback_and_ends():
    out, _ = _call(_Resp(200, {"response_text": "late"}, delay=0.5), timeout=0.1)
    assert out["speech"] == bridge_client.FALLBACK and not out["continue_conversation"]
    assert "timeout" in out["error"]


def test_ha_client_bridge_errors_speak_fallback():
    for resp in (_Resp(500, {}), _Resp(503, {}), _Resp(200, None, bad_json=True),
                 _Resp(200, {"response_text": ""})):
        out, _ = _call(resp)
        assert out["speech"] == bridge_client.FALLBACK and not out["ok"] and not out["continue_conversation"]


def test_ha_client_unknown_device_says_so():
    out, _ = _call(_Resp(404, {"detail": "unknown voice device"}))
    assert out["speech"] == bridge_client.UNKNOWN_DEVICE and not out["continue_conversation"]
