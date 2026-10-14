"""Aria's voice for the Voice PE: text -> speech in the resident session voice.

Home Assistant's text-to-speech step calls this (bridge credential) so a
Voice PE speaks in the same voice as Aria in the room (session_voice:
CAOSCARE_REALTIME_VOICE, e.g. "marin"), not a separate local voice.
Model: CAOSCARE_VOICE_BRIDGE_TTS_MODEL (default gpt-4o-mini-tts).
"""
import logging
import os
from typing import Optional

import httpx
from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from routes.realtime import OPENAI_API_BASE, _require_openai_key, session_voice
from routes.voice_bridge import _check_token

router = APIRouter(prefix="/voice-bridge", tags=["voice-bridge"])
log = logging.getLogger(__name__)


class SpeechInput(BaseModel):
    text: str = Field(min_length=1, max_length=4000)


def tts_model() -> str:
    return (os.environ.get("CAOSCARE_VOICE_BRIDGE_TTS_MODEL") or "gpt-4o-mini-tts").strip()


@router.post("/speech")
async def speech(body: SpeechInput, authorization: Optional[str] = Header(None)):
    """Streams the audio as the provider produces it (the provider speaks at
    roughly real-time pace, so waiting for the whole file delays a long reply
    by its full length)."""
    _check_token(authorization)
    key = _require_openai_key()
    voice = session_voice(None)
    client = httpx.AsyncClient(timeout=httpx.Timeout(10, read=60))
    req = client.build_request("POST", f"{OPENAI_API_BASE}/audio/speech",
                               headers={"Authorization": f"Bearer {key}"},
                               json={"model": tts_model(), "voice": voice, "input": body.text,
                                     "response_format": "mp3"})
    try:
        upstream = await client.send(req, stream=True)
    except httpx.HTTPError as e:
        await client.aclose()
        log.warning("voice bridge speech failed: %s", type(e).__name__)
        raise HTTPException(502, "speech provider unreachable")
    if upstream.status_code != 200:
        await upstream.aclose()
        await client.aclose()
        log.warning("voice bridge speech provider status %s", upstream.status_code)
        raise HTTPException(502, f"speech provider returned {upstream.status_code}")

    async def chunks():
        try:
            async for chunk in upstream.aiter_bytes():
                yield chunk
        except httpx.HTTPError as e:
            log.warning("voice bridge speech stream cut: %s", type(e).__name__)
        finally:
            await upstream.aclose()
            await client.aclose()

    return StreamingResponse(chunks(), media_type="audio/mpeg", headers={"X-Aria-Voice": voice})
