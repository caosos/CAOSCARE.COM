"""Research router — live web research for the Realtime AI tool dispatcher.

Strategy:
  - If PERPLEXITY_API_KEY is set, use Perplexity Sonar for live web answers
    with citations.
  - If Perplexity is unavailable and OPENAI_API_KEY is set, use OpenAI for
    general answers without live-source claims.
  - If no supported provider key is configured, return HTTP 503.
  - In every case, the response is shaped for spoken delivery: short,
    conversational, no bullet points, no markdown.

Endpoint is PUBLIC by design — the tool dispatcher in `useRealtimeVoice.js`
calls it directly from the kiosk during a live conversation. It is
intentionally rate-light to keep latency under the 4-5 second budget that
feels acceptable in a voice exchange.
"""
import os
import logging
from typing import List
import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter(prefix="/research", tags=["research"])
logger = logging.getLogger(__name__)

PERPLEXITY_API_KEY = os.environ.get("PERPLEXITY_API_KEY", "").strip()
PERPLEXITY_ENDPOINT = "https://api.perplexity.ai/chat/completions"
PERPLEXITY_MODEL = "sonar"   # fast, cost-effective; "sonar-pro" for deeper retrieval

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "").strip()
OPENAI_TEXT_MODEL = os.environ.get("OPENAI_TEXT_MODEL", "gpt-4o-mini").strip() or "gpt-4o-mini"
OPENAI_API_BASE = os.environ.get("OPENAI_API_BASE", "https://api.openai.com/v1").rstrip("/")


class ResearchInput(BaseModel):
    question: str = Field(..., min_length=2, max_length=500)


class ResearchOutput(BaseModel):
    answer: str
    citations: List[str] = Field(default_factory=list)
    source: str   # "perplexity" | "openai" | "none"


SYSTEM_PROMPT = (
    "You are CAOS, a calm voice companion for an older adult in their living "
    "room. Answer the resident's question in 2-4 short conversational sentences "
    "they can listen to comfortably. Plain language. No bullet points, no "
    "headings, no markdown. If you cite a source, just mention it naturally "
    "('according to the AP') rather than printing a URL. If you do not know "
    "or are not certain, say so honestly — never invent."
)


async def _ask_perplexity(question: str) -> ResearchOutput:
    payload = {
        "model": PERPLEXITY_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": question},
        ],
        "max_tokens": 400,
        "temperature": 0.4,
    }
    headers = {
        "Authorization": f"Bearer {PERPLEXITY_API_KEY}",
        "Content-Type": "application/json",
    }
    async with httpx.AsyncClient(timeout=25.0) as client:
        r = await client.post(PERPLEXITY_ENDPOINT, json=payload, headers=headers)
        r.raise_for_status()
        data = r.json()
    text = (data.get("choices") or [{}])[0].get("message", {}).get("content", "").strip()
    citations = data.get("citations") or []
    return ResearchOutput(answer=text, citations=citations, source="perplexity")


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
    return ResearchOutput(answer=text, citations=[], source="openai")


async def research_topic(question: str) -> ResearchOutput:
    """Entry point used by the AI tool dispatcher. Tries Perplexity first
    for live sources, then OpenAI for non-live fallback answers."""
    if PERPLEXITY_API_KEY:
        try:
            return await _ask_perplexity(question)
        except httpx.HTTPStatusError as e:
            logger.warning(f"Perplexity HTTP {e.response.status_code}; trying OpenAI fallback")
        except Exception as e:
            logger.warning(f"Perplexity error: {e}; trying OpenAI fallback")
    if OPENAI_API_KEY:
        try:
            return await _ask_openai(question)
        except httpx.HTTPStatusError as e:
            logger.warning(f"OpenAI research HTTP {e.response.status_code}")
        except Exception as e:
            logger.warning(f"OpenAI research error: {e}")
    raise HTTPException(
        status_code=503,
        detail="Research is unavailable; configure PERPLEXITY_API_KEY or OPENAI_API_KEY.",
    )


@router.post("", response_model=ResearchOutput)
async def research_endpoint(data: ResearchInput) -> ResearchOutput:
    if not data.question.strip():
        raise HTTPException(status_code=400, detail="Empty question")
    return await research_topic(data.question.strip())
