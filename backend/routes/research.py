"""Research router - web research for the Realtime AI tool dispatcher.

Provider is chosen explicitly by CAOSCARE_RESEARCH_PROVIDER:
  - "openai_web_search": OpenAI Responses API with the native web_search tool
    (same OPENAI_API_KEY; OPENAI_RESEARCH_MODEL is REQUIRED, no default model;
    optional OPENAI_RESEARCH_TIMEOUT seconds and OPENAI_RESEARCH_REASONING_EFFORT).
    `live` is true only when the response really contains a web_search_call
    AND a url_citation. Misconfiguration -> HTTP 503; provider HTTP error,
    timeout or malformed response -> HTTP 502. A model-only answer is never
    returned as live and there is no silent fallback.
  - "none" / unset (default): no live research. If OPENAI_API_KEY is set a
    plain model answers from general knowledge with live=False, else 503.

ROLLBACK: set CAOSCARE_RESEARCH_PROVIDER=none (or unset it) and restart the
backend. See docs/RESEARCH_PROVIDER.md.

Every call records a CaosEvent (question hash and length only, never the
question text; provider, model, live, citation count, outcome). Spoken
delivery: short, conversational, no bullet points, no markdown.

Endpoint is reachable without login (the kiosk tool dispatcher calls it), but
when a paid provider is enabled it requires a live Aria session or an owner
token and is rate limited - see routes/research_guard.py (RQ-049).
"""
import os
import hashlib
import logging
import time
from typing import List, Optional
import httpx
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from routes.events import log_event
from routes.realtime_truth_rules import live_research_enabled
from routes import research_openai_search as oas
from routes import research_guard

router = APIRouter(prefix="/research", tags=["research"])
logger = logging.getLogger(__name__)

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "").strip()
OPENAI_TEXT_MODEL = os.environ.get("OPENAI_TEXT_MODEL", "gpt-4o-mini").strip() or "gpt-4o-mini"
OPENAI_API_BASE = os.environ.get("OPENAI_API_BASE", "https://api.openai.com/v1").rstrip("/")


class ResearchInput(BaseModel):
    question: str = Field(..., min_length=2, max_length=500)
    resident_id: Optional[str] = Field(default=None, max_length=100)
    session_id: Optional[str] = Field(default=None, max_length=100)


class ResearchOutput(BaseModel):
    answer: str
    citations: List[str] = Field(default_factory=list)   # URLs (existing contract)
    citations_detail: List[dict] = Field(default_factory=list)  # [{url, title}]
    source: str   # "openai_web_search" | "openai" | "none"
    live: bool = False   # True only with a real web_search_call AND a url_citation
    note: Optional[str] = None
    provenance: Optional[dict] = None   # model, response_id, search_call_count, retrieved_at


SYSTEM_PROMPT = (
    "You are CAOS, a calm voice companion for an older adult in their living "
    "room. Answer the resident's question in 2-4 short conversational sentences "
    "they can listen to comfortably. Plain language. No bullet points, no "
    "headings, no markdown. If you cite a source, just mention it naturally "
    "('according to the AP') rather than printing a URL. If the sources "
    "disagree, say you are not certain. If you do not know "
    "or are not certain, say so honestly - never invent."
)


async def _ask_openai_web_search(question: str) -> ResearchOutput:
    p = await oas.ask(question, SYSTEM_PROMPT)
    cites = p["citations"]
    live = p["search_calls"] >= 1 and len(cites) >= 1
    note = None
    if not live:
        note = ("The provider ran no web search." if p["search_calls"] == 0
                else "The web search returned no citable sources.") + \
               " Treat the answer as general knowledge, not a live lookup."
    return ResearchOutput(answer=p["answer"], citations=[c["url"] for c in cites],
                          citations_detail=cites, source=oas.SOURCE, live=live,
                          note=note, provenance=p["provenance"])


async def _ask_openai(question: str) -> ResearchOutput:
    payload = {
        "model": OPENAI_TEXT_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT + (
                "\n\nYou do not have live web access in this fallback path. "
                "If the question depends on current facts, say you cannot verify it right now."
            )},
            {"role": "user", "content": question},
        ],
        "max_tokens": 400,
        "temperature": 0.4,
    }
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json",
    }
    async with httpx.AsyncClient(timeout=25.0) as client:
        r = await client.post(f"{OPENAI_API_BASE}/chat/completions", json=payload, headers=headers)
        r.raise_for_status()
        data = r.json()
    text = (data.get("choices") or [{}])[0].get("message", {}).get("content", "").strip()
    return ResearchOutput(answer=text, citations=[], source="openai", live=False)


async def _run(question: str) -> ResearchOutput:
    if oas.provider_name() == oas.SOURCE:
        problem = oas.config_problem()
        if problem:
            raise HTTPException(status_code=503, detail=f"Research provider openai_web_search is not configured: {problem}")
        try:
            return await _ask_openai_web_search(question)
        except oas.ResearchProviderError as e:
            raise HTTPException(status_code=e.status, detail=e.detail)
    if OPENAI_API_KEY:
        try:
            return await _ask_openai(question)
        except httpx.HTTPStatusError as e:
            logger.warning(f"OpenAI research HTTP {e.response.status_code}")
        except Exception as e:
            logger.warning(f"OpenAI research error: {e}")
    raise HTTPException(
        status_code=503,
        detail="Research is unavailable; set CAOSCARE_RESEARCH_PROVIDER=openai_web_search "
               "(with OPENAI_API_KEY and OPENAI_RESEARCH_MODEL) or OPENAI_API_KEY for general answers.",
    )


async def research_topic(question: str) -> ResearchOutput:
    """Entry point used by the AI tool dispatcher; records one event per call."""
    started = time.monotonic()
    meta = {"provider": oas.provider_name(), "live_enabled": live_research_enabled(),
            "model": oas.search_model() or None,
            "question_sha256": hashlib.sha256(question.encode()).hexdigest()[:16],
            "question_length": len(question)}
    try:
        out = await _run(question)
    except HTTPException as e:
        await log_event(event_type="research_lookup", source="resident_aria", target_type="tool",
                        action="research_topic", status="failed", error_code=str(e.status_code),
                        error_message=str(e.detail)[:200], metadata={**meta, "live": False},
                        duration_ms=(time.monotonic() - started) * 1000)
        raise
    prov = out.provenance or {}
    await log_event(event_type="research_lookup", source="resident_aria", target_type="tool",
                    action="research_topic", status="succeeded",
                    verification_status="verified" if out.live else "unverified",
                    metadata={**meta, "live": out.live, "result_source": out.source,
                              "citation_count": len(out.citations),
                              "search_call_count": prov.get("search_call_count"),
                              "response_id": prov.get("response_id")},
                    duration_ms=(time.monotonic() - started) * 1000)
    return out


@router.post("", response_model=ResearchOutput)
async def research_endpoint(data: ResearchInput, request: Request) -> ResearchOutput:
    if not data.question.strip():
        raise HTTPException(status_code=400, detail="Empty question")
    # RQ-049: paid provider -> live session (or owner) required, rate limited.
    await research_guard.enforce(request, data.resident_id, data.session_id)
    return await research_topic(data.question.strip())
