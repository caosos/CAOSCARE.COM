"""Research router — live web research for the Realtime AI tool dispatcher.

Strategy:
  - If PERPLEXITY_API_KEY is set, use Perplexity Sonar (real-time web search +
    citations). This is the gold standard for "tell me what's happening with…"
    style questions.
  - If not, fall back to Claude Sonnet 4.5 (no web access — answers from
    training data only). The companion will say so honestly when asked about
    very recent events. No silent failure.
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

EMERGENT_LLM_KEY = os.environ.get("EMERGENT_LLM_KEY", "").strip()


class ResearchInput(BaseModel):
    question: str = Field(..., min_length=2, max_length=500)


class ResearchOutput(BaseModel):
    answer: str
    citations: List[str] = Field(default_factory=list)
    source: str   # "perplexity" | "claude" | "none"


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


async def _ask_claude(question: str) -> ResearchOutput:
    """Fallback: Claude Sonnet 4.5 via the Emergent universal key. No web
    search — purely training-data answers, but still useful for general
    knowledge, jokes, history, recipes, prayers, life-history conversation."""
    if not EMERGENT_LLM_KEY:
        return ResearchOutput(
            answer="I don't have web access right now, so I can only tell you what I already know — and I'd rather not guess on this one.",
            citations=[],
            source="none",
        )
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        chat = (
            LlmChat(
                api_key=EMERGENT_LLM_KEY,
                session_id=f"research_{question[:20]}",
                system_message=SYSTEM_PROMPT + (
                    "\n\nIMPORTANT: you do NOT have live web access. If the resident "
                    "asks about something that happened recently (this week, today, "
                    "last night), gently say you don't have today's news. Do not "
                    "invent facts."
                ),
            )
            .with_model("anthropic", "claude-sonnet-4-5-20250929")
        )
        text = await chat.send_message(UserMessage(text=question))
        return ResearchOutput(answer=(text or "").strip(), citations=[], source="claude")
    except Exception as e:
        logger.error(f"Claude research fallback failed: {e}")
        return ResearchOutput(
            answer="I'm sorry — I'm having trouble reaching what I'd usually look up for this. Let's come back to it.",
            citations=[],
            source="none",
        )


async def research_topic(question: str) -> ResearchOutput:
    """Entry-point used by the AI tool dispatcher. Tries Perplexity first
    (live web), falls back to Claude (training-data) if no key or on error."""
    if PERPLEXITY_API_KEY:
        try:
            return await _ask_perplexity(question)
        except httpx.HTTPStatusError as e:
            logger.warning(f"Perplexity HTTP {e.response.status_code} — falling back to Claude")
        except Exception as e:
            logger.warning(f"Perplexity error: {e} — falling back to Claude")
    return await _ask_claude(question)


@router.post("", response_model=ResearchOutput)
async def research_endpoint(data: ResearchInput) -> ResearchOutput:
    if not data.question.strip():
        raise HTTPException(status_code=400, detail="Empty question")
    return await research_topic(data.question.strip())
