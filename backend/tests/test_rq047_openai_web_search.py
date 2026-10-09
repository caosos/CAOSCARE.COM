"""RQ-047: OpenAI Responses API web search as the research backend.
The provider is MOCKED (httpx stub) - no network, no paid call."""
import asyncio
import os
import sys

import httpx
import pytest
from fastapi import HTTPException

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from routes import research
from routes import research_openai_search as oas
from routes.realtime_truth_rules import live_research_enabled, research_tool_description


def _cfg(monkeypatch, provider="openai_web_search", key="k", model="m"):
    for name, val in (("CAOSCARE_RESEARCH_PROVIDER", provider), ("OPENAI_API_KEY", key), ("OPENAI_RESEARCH_MODEL", model)):
        if val is None:
            monkeypatch.delenv(name, raising=False)
        else:
            monkeypatch.setenv(name, val)


def _payload(searches=1, cites=({"url": "https://a.test/1", "title": "A"},), text="Per A, yes.", dup=False):
    ann = [{"type": "url_citation", "url": c["url"], "title": c["title"], "start_index": 0, "end_index": 3} for c in cites]
    if dup and ann:
        ann.append(dict(ann[0]))
    out = [{"type": "web_search_call", "id": f"ws_{i}", "status": "completed"} for i in range(searches)]
    out.append({"type": "message", "role": "assistant",
                "content": [{"type": "output_text", "text": text, "annotations": ann}]})
    return {"id": "resp_1", "model": "m-2026", "output": out}


class _Resp:
    def __init__(self, status=200, data=None, bad_json=False):
        self.status_code, self._d, self._bad = status, data, bad_json
    def json(self):
        if self._bad:
            raise ValueError("bad")
        return self._d


def _stub(monkeypatch, resp=None, exc=None, seen=None):
    class C:
        def __init__(self, *a, **k): self.timeout = k.get("timeout")
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        async def post(self, url, json=None, headers=None):
            if seen is not None:
                seen.append({"url": url, "json": json, "headers": headers})
            if exc:
                raise exc
            return resp
    monkeypatch.setattr(oas.httpx, "AsyncClient", C)


@pytest.fixture(autouse=True)
def events(monkeypatch):
    got = []

    async def _log(**k):
        got.append(k)
        return k
    monkeypatch.setattr(research, "log_event", _log)
    return got


def _run(q="who is the mayor"):
    return asyncio.run(research.research_topic(q))


def test_live_success_with_citations(monkeypatch, events):
    _cfg(monkeypatch)
    seen = []
    _stub(monkeypatch, _Resp(data=_payload(dup=True)), seen=seen)
    out = _run()
    assert out.live is True and out.source == "openai_web_search" and out.note is None
    assert out.citations == ["https://a.test/1"] and out.citations_detail == [{"url": "https://a.test/1", "title": "A"}]
    p = out.provenance
    assert p["model"] == "m-2026" and p["response_id"] == "resp_1" and p["search_call_count"] == 1 and p["retrieved_at"]
    body = seen[0]["json"]
    assert seen[0]["url"].endswith("/responses") and body["model"] == "m" and body["tools"] == [{"type": "web_search"}]
    assert "reasoning" not in body
    assert seen[0]["headers"]["Authorization"] == "Bearer k"
    ev = events[-1]
    assert ev["status"] == "succeeded" and ev["metadata"]["live"] is True and ev["metadata"]["citation_count"] == 1
    assert "who is the mayor" not in str(ev) and ev["metadata"]["question_length"] == 16


def test_search_without_citations_not_live(monkeypatch):
    _cfg(monkeypatch)
    _stub(monkeypatch, _Resp(data=_payload(searches=1, cites=())))
    out = _run()
    assert out.live is False and out.citations == [] and "no citable sources" in out.note


def test_no_search_call_not_live(monkeypatch):
    _cfg(monkeypatch)
    _stub(monkeypatch, _Resp(data=_payload(searches=0)))
    out = _run()
    assert out.live is False and "ran no web search" in out.note


@pytest.mark.parametrize("resp,exc,detail", [
    (_Resp(status=429, data={}), None, "HTTP 429"),
    (_Resp(status=500, data={}), None, "HTTP 500"),
    (None, httpx.ReadTimeout("t"), "timed out"),
    (_Resp(bad_json=True), None, "invalid JSON"),
    (_Resp(data={"nope": 1}), None, "malformed"),
    (_Resp(data={"output": [{"type": "message", "content": []}]}), None, "no answer text"),
])
def test_provider_failures_are_502(monkeypatch, events, resp, exc, detail):
    _cfg(monkeypatch)
    _stub(monkeypatch, resp, exc)
    with pytest.raises(HTTPException) as e:
        _run()
    assert e.value.status_code == 502 and detail in e.value.detail
    assert events[-1]["status"] == "failed" and events[-1]["metadata"]["live"] is False


def test_not_configured_is_503(monkeypatch, events):
    _cfg(monkeypatch, provider="none", key=None)
    monkeypatch.setattr(research, "OPENAI_API_KEY", "")
    with pytest.raises(HTTPException) as e:
        _run()
    assert e.value.status_code == 503 and "CAOSCARE_RESEARCH_PROVIDER" in e.value.detail
    assert events[-1]["status"] == "failed"


def test_missing_model_clear_error(monkeypatch):
    _cfg(monkeypatch, model=None)
    assert live_research_enabled() is False
    with pytest.raises(HTTPException) as e:
        _run()
    assert e.value.status_code == 503 and "OPENAI_RESEARCH_MODEL" in e.value.detail


def test_live_enabled_needs_provider_key_and_model(monkeypatch):
    _cfg(monkeypatch)
    assert live_research_enabled() is True and "live web" in research_tool_description()
    _cfg(monkeypatch, provider="none")
    assert live_research_enabled() is False and "NOT a live lookup" in research_tool_description()
    _cfg(monkeypatch, key=None)
    assert live_research_enabled() is False
    _cfg(monkeypatch, model="")
    assert live_research_enabled() is False


def test_timeout_and_effort_env(monkeypatch):
    _cfg(monkeypatch)
    monkeypatch.setenv("OPENAI_RESEARCH_REASONING_EFFORT", "low")
    seen = []
    _stub(monkeypatch, _Resp(data=_payload()), seen=seen)
    _run()
    assert seen[0]["json"]["reasoning"] == {"effort": "low"}


def test_dispatch_shapes_match_payload(monkeypatch):
    """Backend payload as the kiosk receives it -> frontend contract fields."""
    _cfg(monkeypatch)
    _stub(monkeypatch, _Resp(data=_payload()))
    j = _run().model_dump()
    assert j["live"] is True and j["source"] == "openai_web_search" and j["citations"]
