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
from fastapi import APIRouter, Header, HTTPException, Response
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
    _check_token(authorization)
    key = _require_openai_key()
    voice = session_voice(None)
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.post(f"{OPENAI_API_BASE}/audio/speech",
                                  headers={"Authorization": f"Bearer {key}"},
                                  json={"model": tts_model(), "voice": voice, "input": body.text,
                                        "response_format": "mp3"})
    except httpx.HTTPError as e:
        log.warning("voice bridge speech failed: %s", type(e).__name__)
        raise HTTPException(502, "speech provider unreachable")
    if r.status_code != 200:
        log.warning("voice bridge speech provider status %s", r.status_code)
        raise HTTPException(502, f"speech provider returned {r.status_code}")
    return Response(content=r.content, media_type="audio/mpeg", headers={"X-Aria-Voice": voice})
