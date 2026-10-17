"""OpenAI Responses API web search provider for `research_topic` (RQ-047).

Provider facts (OpenAI docs, read 2026-10-09): POST {OPENAI_API_BASE}/responses
with `tools: [{"type": "web_search"}]`. The response `output` array holds
`web_search_call` items and a `message` item whose `output_text` content carries
`url_citation` annotations (url, title, start_index, end_index). Web search is
not supported with minimal reasoning. Prices are not recorded here.

An answer is "live" only when the response really contains at least one
web_search_call AND at least one url_citation. Anything else is returned as
not live, with a note. Errors are raised as `ResearchProviderError`; the
caller maps them to HTTP 502/503 and never invents text.
"""
import os
from datetime import datetime, timezone
from typing import Optional

import httpx

SOURCE = "openai_web_search"
DEFAULT_TIMEOUT = 25.0


class ResearchProviderError(Exception):
    def __init__(self, status: int, detail: str):
        super().__init__(detail)
        self.status = status
        self.detail = detail


def provider_name() -> str:
    return os.environ.get("CAOSCARE_RESEARCH_PROVIDER", "none").strip().lower() or "none"


def search_model() -> str:
    return os.environ.get("OPENAI_RESEARCH_MODEL", "").strip()


def search_configured() -> bool:
    """Single check: provider selected AND key AND model all set."""
    return (provider_name() == SOURCE
            and bool(os.environ.get("OPENAI_API_KEY", "").strip())
            and bool(search_model()))


def config_problem() -> Optional[str]:
    """Why openai_web_search cannot run, or None."""
    if not os.environ.get("OPENAI_API_KEY", "").strip():
        return "OPENAI_API_KEY is not set."
    if not search_model():
        return "OPENAI_RESEARCH_MODEL is not set; no default model is assumed."
    return None


def _timeout() -> float:
    try:
        t = float(os.environ.get("OPENAI_RESEARCH_TIMEOUT", ""))
        return t if t > 0 else DEFAULT_TIMEOUT
    except ValueError:
        return DEFAULT_TIMEOUT


def _usage_counts(data: dict) -> dict:
    """Keep provider billing counts, never request/response content."""
    raw = data.get("usage") if isinstance(data, dict) else None
    if not isinstance(raw, dict):
        return {}
    input_detail = raw.get("input_tokens_details") or {}
    output_detail = raw.get("output_tokens_details") or {}

    def count(value):
        return value if isinstance(value, int) and value >= 0 else 0

    return {
        "input_tokens": count(raw.get("input_tokens")),
        "cached_input_tokens": count(input_detail.get("cached_tokens")),
        "output_tokens": count(raw.get("output_tokens")),
        "reasoning_output_tokens": count(output_detail.get("reasoning_tokens")),
        "total_tokens": count(raw.get("total_tokens")),
    }


def parse_response(data: dict) -> dict:
    """Extract answer, deduplicated citations and the search-call count."""
    out = data.get("output") if isinstance(data, dict) else None
    if not isinstance(out, list):
        raise ResearchProviderError(502, "Research provider returned a malformed response.")
    if data.get("error"):
        raise ResearchProviderError(502, "Research provider reported an error.")
    searches, texts, cites, seen = 0, [], [], set()
    for item in out:
        if not isinstance(item, dict):
            continue
        if item.get("type") == "web_search_call":
            searches += 1
        elif item.get("type") == "message":
            for part in item.get("content") or []:
                if not isinstance(part, dict) or part.get("type") != "output_text":
                    continue
                if isinstance(part.get("text"), str):
                    texts.append(part["text"])
                for a in part.get("annotations") or []:
                    url = a.get("url") if isinstance(a, dict) and a.get("type") == "url_citation" else None
                    if url and url not in seen:
                        seen.add(url)
                        cites.append({"url": url, "title": a.get("title") or ""})
    answer = " ".join(t.strip() for t in texts).strip()
    if not answer:
        raise ResearchProviderError(502, "Research provider returned no answer text.")
    return {"answer": answer, "citations": cites, "search_calls": searches}


async def ask(question: str, instructions: str) -> dict:
    """One Responses API call. Returns parsed result + provenance."""
    key = os.environ.get("OPENAI_API_KEY", "").strip()
    model = search_model()
    base = os.environ.get("OPENAI_API_BASE", "https://api.openai.com/v1").rstrip("/")
    body = {
        "model": model,
        "instructions": instructions,
        "input": question,
        "tools": [{"type": "web_search", "external_web_access": True}],
        "tool_choice": "required",
        # Resident questions are sensitive. Responses are not retained by the
        # provider after this request; CAOSCare keeps only its own private,
        # scoped operational evidence.
        "store": False,
    }
    effort = os.environ.get("OPENAI_RESEARCH_REASONING_EFFORT", "").strip()
    if effort:
        body["reasoning"] = {"effort": effort}
    from routes.paid_api_receipts import record_request_async, now_iso   # paid API receipt (paid_api_ledger.py)
    _t0, r = now_iso(), None
    try:
        async with httpx.AsyncClient(timeout=_timeout()) as client:
            r = await client.post(f"{base}/responses", json=body,
                                  headers={"Authorization": f"Bearer {key}",
                                           "Content-Type": "application/json"})
    except httpx.TimeoutException:
        raise ResearchProviderError(502, "Research provider timed out.")
    except httpx.HTTPError as e:
        raise ResearchProviderError(502, f"Research provider unreachable ({type(e).__name__}).")
    finally:
        await record_request_async(r, started_at=_t0, purpose="live_research", endpoint="responses",
                                   model_requested=model, key=key)
    if r.status_code >= 400:
        raise ResearchProviderError(502, f"Research provider returned HTTP {r.status_code}.")
    try:
        data = r.json()
    except ValueError:
        raise ResearchProviderError(502, "Research provider returned invalid JSON.")
    parsed = parse_response(data)
    parsed["provenance"] = {
        "model": data.get("model") or model,
        "response_id": data.get("id"),
        "search_call_count": parsed["search_calls"],
        "usage": _usage_counts(data),
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
    }
    return parsed
