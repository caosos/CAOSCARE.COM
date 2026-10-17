"""Every paid OpenAI call path writes a durable paid API receipt (paid_api_ledger.py) - offline, fake providers.

A socket guard fails any test that tries to leave this machine, so these tests cannot make a paid request."""
import asyncio
import io
import re
import socket
import uuid
from pathlib import Path

import pytest

import paid_api_ledger as L
from routes import paid_api_receipts as R

run = asyncio.get_event_loop().run_until_complete
ROUTES = Path(__file__).resolve().parents[1] / "routes"
CHAT_USAGE = {"prompt_tokens": 1200, "completion_tokens": 80, "prompt_tokens_details": {"cached_tokens": 1000}}
SECRET_KEY = "sk-test-not-a-real-key-1234567890"


@pytest.fixture(autouse=True)
def no_external_network(monkeypatch):
    real = socket.socket.connect

    def guarded(self, addr):
        host = addr[0] if isinstance(addr, tuple) else str(addr)
        if host not in ("127.0.0.1", "::1", "localhost"):
            raise AssertionError(f"test tried to reach {host} - no provider request is allowed in tests")
        return real(self, addr)
    monkeypatch.setattr(socket.socket, "connect", guarded)


@pytest.fixture
def lg(monkeypatch):
    ledger = L.PaidApiLedger(None, f"caoscare_ledger_test_{uuid.uuid4().hex[:8]}")
    monkeypatch.setattr(R, "_ledger", ledger)
    yield ledger
    ledger.db.client.drop_database(ledger.db.name)


class Resp:
    def __init__(self, status=200, body=None, content=b"", headers=None):
        self.status_code, self._body, self.content = status, body, content
        self.headers = {"x-request-id": "req_fake", **({"content-type": "application/json"} if body is not None else {}),
                        **(headers or {})}
        self.text = "" if body is None else str(body)

    def json(self):
        return self._body

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(self.status_code)


def fake_requests(monkeypatch, module, resp):
    sent = []

    def post(url, **kw):
        sent.append(url)
        if isinstance(resp, Exception):
            raise resp
        return resp
    monkeypatch.setattr(module.requests, "post", post)
    return sent


def fake_httpx(monkeypatch, module, resp):
    class Client:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, url, **kw):
            return resp
    monkeypatch.setattr(module.httpx, "AsyncClient", Client)


def only_receipt(lg, **q):
    rows = list(lg.db.receipts.find(q, {"_id": 0}))
    assert len(rows) == 1, rows
    r = rows[0]
    assert SECRET_KEY not in repr(r)              # never the key itself
    return r


# -- the inventory: no provider call site in routes/ without a receipt -------------------------------------

PROVIDER_CALL = re.compile(r"(requests\.post|client\.post|client\.stream|websockets\.connect)\(")
RECORDERS = re.compile(r"record_(request|request_async|mint|connect|phone_call|realtime_event)\(")


def test_every_openai_call_site_in_routes_writes_a_receipt():
    uncovered = []
    for f in sorted(ROUTES.glob("*.py")):
        src = f.read_text()
        if "openai" not in src.lower() or f.name == "paid_api_receipts.py":
            continue
        calls = len(PROVIDER_CALL.findall(src))
        if not calls or not re.search(r"OPENAI_API_BASE|_openai_base\(\)|api\.openai\.com|base\}/responses|OPENAI_REALTIME_WS", src):
            continue
        if f.name == "phone_aria_sideband.py":   # the socket's events are receipted by record_realtime_event
            calls = 1
        if len(RECORDERS.findall(src)) < calls:
            uncovered.append(f"{f.name}: {calls} provider call(s), {len(RECORDERS.findall(src))} receipt call(s)")
    assert uncovered == []


# -- each path, with a fake provider -----------------------------------------------------------------------

def test_memory_extraction_and_conversation_summary(lg, monkeypatch):
    from routes import memory, aria_life_memory
    monkeypatch.setattr(memory, "OPENAI_API_KEY", SECRET_KEY)
    fake_requests(monkeypatch, memory, Resp(body={"id": "chatcmpl_1", "model": "gpt-4o-mini-2024-07-18",
                                                 "usage": CHAT_USAGE, "choices": [{"message": {"content": "[]"}}]}))
    run(memory._openai_chat("sys", "user"))
    r = only_receipt(lg, provider_response_id="chatcmpl_1")
    assert r["kind"] == "provider_request" and r["provenance"]["purpose"] == "memory_extraction"
    assert r["model_provider"] == "gpt-4o-mini-2024-07-18" and r["usage"] == CHAT_USAGE
    assert r["estimate"]["usd"] == round((200 * .15 + 1000 * .075 + 80 * .60) / 1e6, 8)
    assert r["key_id"] == L.key_id(SECRET_KEY) and r["endpoint"] == "chat/completions" and r["status"] == 200
    fake_requests(monkeypatch, memory, Resp(body={"id": "chatcmpl_2", "usage": CHAT_USAGE, "choices": [{}]}))
    run(aria_life_memory._chat("sys", "user"))
    assert only_receipt(lg, provider_response_id="chatcmpl_2")["provenance"]["purpose"] == "conversation_summary"


def test_ai_chat_alert_classifier_speech_generation_and_transcription(lg, monkeypatch):
    from routes import ai
    from models import TTSInput
    monkeypatch.setattr(ai, "OPENAI_API_KEY", SECRET_KEY)
    fake_requests(monkeypatch, ai, Resp(body={"id": "c_chat", "usage": CHAT_USAGE, "choices": [{}]}))
    run(ai._openai_chat("s", "u"))
    fake_requests(monkeypatch, ai, Resp(body={"id": "c_cls", "usage": CHAT_USAGE, "choices": [{}]}))
    run(ai._openai_chat("s", "u", response_format={"type": "json_object"}, purpose="alert_classification"))
    assert only_receipt(lg, provider_response_id="c_chat")["provenance"]["purpose"] == "admin_ai_chat"
    assert only_receipt(lg, provider_response_id="c_cls")["provenance"]["purpose"] == "alert_classification"

    fake_requests(monkeypatch, ai, Resp(content=b"mp3", headers={"x-request-id": "req_tts"}))
    run(ai.tts(TTSInput(text="Hello there")))
    t = only_receipt(lg, provider_response_id="req_tts")
    assert t["provenance"]["purpose"] == "speech_generation" and t["usage"] is None and t["usage_status"] == "unknown"
    assert t["estimate"] == {"usd": round(11 * 15 / 1e6, 8), "pricing_version": L.PRICING_VERSION, "basis": "request_size"}

    from starlette.datastructures import UploadFile
    fake_requests(monkeypatch, ai, Resp(body={"text": "hi"}, headers={"x-request-id": "req_stt"}))
    run(ai.stt(UploadFile(io.BytesIO(b"RIFF"), filename="a.wav"), user={"role": "admin"}))
    s = only_receipt(lg, provider_response_id="req_stt")
    assert s["provenance"]["purpose"] == "speech_transcription" and s["model_requested"] == "whisper-1"
    assert s["usage"] is None and s["estimate"]["usd"] is None          # no usage, no duration: unknown, not 0


def test_vision_and_haiku(lg, monkeypatch):
    from routes import vision, haiku
    monkeypatch.setattr(vision, "OPENAI_API_KEY", SECRET_KEY)
    fake_requests(monkeypatch, vision, Resp(body={"id": "c_vis", "usage": CHAT_USAGE, "choices": [{}]}))
    vision._post_openai_vision("what is this", "AAAA")
    fake_requests(monkeypatch, vision, Resp(content=b"mp3", headers={"x-request-id": "req_vtts"}))
    vision._post_openai_tts("ok")
    monkeypatch.setattr(haiku, "OPENAI_API_KEY", SECRET_KEY)
    fake_requests(monkeypatch, haiku, Resp(body={"id": "c_hk", "usage": CHAT_USAGE, "choices": [{}]}))
    haiku._post_openai_chat("s", "u")
    assert only_receipt(lg, provider_response_id="c_vis")["provenance"]["purpose"] == "vision_description"
    assert only_receipt(lg, provider_response_id="req_vtts")["provenance"]["purpose"] == "speech_generation"
    assert only_receipt(lg, provider_response_id="c_hk")["provenance"]["purpose"] == "haiku_generation"


def test_research_live_lookup_and_admin_assistant(lg, monkeypatch):
    from routes import research, research_openai_search as oas, admin_assistant
    monkeypatch.setattr(research, "OPENAI_API_KEY", SECRET_KEY)
    fake_httpx(monkeypatch, research, Resp(body={"id": "c_res", "usage": CHAT_USAGE, "choices": [{"message": {"content": "x"}}]}))
    run(research._ask_openai("q"))
    monkeypatch.setenv("OPENAI_API_KEY", SECRET_KEY)
    monkeypatch.setenv("OPENAI_RESEARCH_MODEL", "gpt-4.1-mini")
    body = {"id": "resp_live", "model": "gpt-4.1-mini-2025-04-14", "output": [{"type": "web_search_call"}],
            "usage": {"input_tokens": 8629, "output_tokens": 81, "input_tokens_details": {"cached_tokens": 0}}}
    fake_httpx(monkeypatch, oas, Resp(body=body))
    try:
        run(oas.ask("q", "instr"))
    except Exception:   # parsing a minimal fake body may fail after the request; the receipt must still exist
        pass
    monkeypatch.setattr(admin_assistant, "OPENAI_API_KEY", SECRET_KEY)
    fake_httpx(monkeypatch, admin_assistant, Resp(body={"id": "c_adm", "usage": CHAT_USAGE, "choices": [{}]}))
    run(admin_assistant._chat_completion([], []))
    assert only_receipt(lg, provider_response_id="c_res")["provenance"]["purpose"] == "research_answer"
    live = only_receipt(lg, provider_response_id="resp_live")
    assert live["provenance"]["purpose"] == "live_research" and live["model_requested"] == "gpt-4.1-mini"
    assert live["estimate"]["usd"] == round((8629 * .40 + 81 * 1.60) / 1e6 + 0.01, 8)   # tokens + one search call
    assert only_receipt(lg, provider_response_id="c_adm")["provenance"]["purpose"] == "admin_assistant"


def test_phone_accept_is_billable_and_control_calls_are_not(lg, monkeypatch):
    from routes import phone_aria
    monkeypatch.setenv("OPENAI_API_KEY", SECRET_KEY)
    fake_httpx(monkeypatch, phone_aria, Resp(status=200, body={}))
    run(phone_aria.openai_post("/realtime/calls/rtc_9/accept", {"model": "gpt-realtime-2.1-mini"}))
    run(phone_aria.openai_post("/realtime/calls/rtc_9/hangup", {}))
    a = only_receipt(lg, kind="session_connected")
    h = only_receipt(lg, kind="provider_control")
    assert a["billable_activity"] is True and a["provider_call_id"] == "rtc_9" and a["provenance"]["purpose"] == "phone_aria"
    assert h["billable_activity"] is False and h["endpoint"] == "hangup"


def test_backend_held_socket_usage_and_transcription(lg):
    state = {}
    U = {"input_token_details": {"text_tokens": 900, "audio_tokens": 20, "cached_tokens": 0,
                                 "cached_tokens_details": {"text_tokens": 0, "audio_tokens": 0}},
         "output_token_details": {"text_tokens": 30, "audio_tokens": 60}}
    ev = lambda m: run(R.record_realtime_event(m, session_id="call_1", purpose="phone_aria",
                                               model="gpt-realtime-2.1-mini", state=state))
    ev({"type": "session.created", "session": {"id": "sess_p", "model": "gpt-realtime-2.1-mini"}})
    ev({"type": "response.done", "response": {"id": "resp_p1", "status": "completed", "usage": U}})
    ev({"type": "conversation.item.input_audio_transcription.completed", "item_id": "item_1",
        "usage": {"type": "tokens", "input_tokens": 40, "output_tokens": 6}})
    ev({"type": "conversation.item.input_audio_transcription.completed", "item_id": "item_2"})   # no usage sent
    ev({"type": "conversation.item.input_audio_transcription.completed", "item_id": "item_1",
        "usage": {"type": "tokens", "input_tokens": 40, "output_tokens": 6}})                    # repeated event
    p = only_receipt(lg, provider_response_id="resp_p1")
    assert p["provenance"]["purpose"] == "phone_aria" and p["provider_session_id"] == "sess_p"
    t1 = only_receipt(lg, provider_response_id="transcription:item_1", counted=True)
    assert t1["provenance"]["purpose"] == "speech_transcription" and t1["estimate"]["usd"] == round((40 * 2.5 + 6 * 10) / 1e6, 8)
    t2 = only_receipt(lg, provider_response_id="transcription:item_2")
    assert t2["usage"] is None and t2["usage_status"] == "unknown" and t2["estimate"]["usd"] is None
    assert lg.db.receipts.count_documents({"provider_response_id": "transcription:item_1", "counted": False}) == 1


def test_room_usage_inherits_room214_conversation_and_transcription_is_its_own_purpose(lg):
    lg.record("session_token_minted", session_id="rt_214", provenance=L.provenance("room214_conversation", room="214"))
    meta = {"usage": {"input_token_details": {"text_tokens": 10, "audio_tokens": 0, "cached_tokens": 0,
                                              "cached_tokens_details": {"text_tokens": 0, "audio_tokens": 0}},
                      "output_token_details": {"text_tokens": 2, "audio_tokens": 3}}, "model": "gpt-realtime-2.1-mini"}
    run(R.record_diagnostic("response_done", "rt_214", "resp_r1", meta))
    run(R.record_diagnostic("transcription_usage", "rt_214", "item_r1",
                            {"usage": {"type": "tokens", "input_tokens": 12, "output_tokens": 3}, "model": "gpt-4o-transcribe"}))
    r = only_receipt(lg, provider_response_id="resp_r1")
    assert r["provenance"]["purpose"] == "room214_conversation" and r["provenance"]["room"] == "214"
    t = only_receipt(lg, provider_response_id="transcription:item_r1")
    assert t["provenance"]["purpose"] == "speech_transcription" and t["provenance"]["conversation_purpose"] == "room214_conversation"
    assert R.session_purpose("214") == "room214_conversation" and R.session_purpose("101") == "resident_conversation"
    assert R.session_purpose(owner=True) == "owner_aria"


def test_a_request_that_never_returns_is_still_receipted(lg, monkeypatch):
    from routes import haiku
    monkeypatch.setattr(haiku, "OPENAI_API_KEY", SECRET_KEY)
    fake_requests(monkeypatch, haiku, TimeoutError("provider timed out"))
    with pytest.raises(TimeoutError):
        haiku._post_openai_chat("s", "u")
    r = only_receipt(lg, kind="provider_request")
    assert r["status"] == "error" and r["usage"] is None and r["usage_status"] == "unknown"
    assert r["provider_response_id"].startswith("local_") and r["provenance"]["purpose"] == "haiku_generation"


def test_a_failed_request_keeps_only_an_error_code_never_the_body(lg, monkeypatch):
    from routes import haiku
    monkeypatch.setattr(haiku, "OPENAI_API_KEY", SECRET_KEY)
    fake_requests(monkeypatch, haiku, Resp(status=429, body={"error": {"code": "rate_limit_exceeded",
                                                                       "message": "private detail"}}))
    with pytest.raises(Exception):
        haiku._post_openai_chat("s", "u")
    r = only_receipt(lg, kind="provider_request")
    assert r["status"] == 429 and r["failure"] == "rate_limit_exceeded" and "private detail" not in repr(r)
