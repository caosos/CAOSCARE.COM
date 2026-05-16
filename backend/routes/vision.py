"""AI vision - OpenAI image understanding for glasses / camera devices.

The Android vision companion app (running on Vuzix M400 or any Android with a camera)
captures frames + audio, forwards them via BLE to the wall-mounted tablet (kiosk),
which POSTs them here. OpenAI describes the scene or answers the resident's spoken
question. TTS audio is generated and streamed back through the earbuds.
"""
import os
import base64
import binascii
import asyncio
import requests
from fastapi import APIRouter, HTTPException
from models import VisionFrameInput

router = APIRouter(prefix="/vision", tags=["vision"])
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "").strip()
OPENAI_TEXT_MODEL = os.environ.get("OPENAI_TEXT_MODEL", "gpt-4o-mini").strip() or "gpt-4o-mini"
OPENAI_VOICE = os.environ.get("OPENAI_VOICE", "sage").strip() or "sage"
OPENAI_API_BASE = os.environ.get("OPENAI_API_BASE", "https://api.openai.com/v1").rstrip("/")


def _require_openai_key() -> str:
    if not OPENAI_API_KEY:
        raise HTTPException(
            status_code=503,
            detail="OPENAI_API_KEY is not configured; OpenAI vision endpoints are unavailable.",
        )
    return OPENAI_API_KEY


def _post_openai_vision(prompt: str, image_base64: str) -> str:
    key = _require_openai_key()
    resp = requests.post(
        f"{OPENAI_API_BASE}/chat/completions",
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        json={
            "model": OPENAI_TEXT_MODEL,
            "messages": [
                {"role": "system", "content": VISION_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_base64}"}},
                    ],
                },
            ],
        },
        timeout=60,
    )
    if resp.status_code >= 400:
        raise HTTPException(status_code=502, detail=f"OpenAI vision failed: {resp.text[:300]}")
    data = resp.json()
    return (data.get("choices") or [{}])[0].get("message", {}).get("content", "")


async def _openai_vision(prompt: str, image_base64: str) -> str:
    return await asyncio.to_thread(_post_openai_vision, prompt, image_base64)


def _post_openai_tts(text: str) -> str:
    key = _require_openai_key()
    resp = requests.post(
        f"{OPENAI_API_BASE}/audio/speech",
        headers={"Authorization": f"Bearer {key}"},
        json={"model": "tts-1", "voice": OPENAI_VOICE, "input": text, "response_format": "mp3"},
        timeout=60,
    )
    if resp.status_code >= 400:
        raise HTTPException(status_code=502, detail=f"OpenAI vision TTS failed: {resp.text[:300]}")
    return base64.b64encode(resp.content).decode("ascii")

VISION_SYSTEM_PROMPT = """You are CAOS, a visual companion for a visually impaired or
low-vision senior. You describe what the camera sees, warn about obstacles, and
answer their questions aloud in short, clear sentences.

RULES
- Speak in short, natural sentences. No markdown. No bullets.
- Prioritize safety: if you see stairs, a closed door, an obstacle in the path, a
  wet floor, or a person blocking the way, mention it FIRST and briefly.
- Use left / right / ahead / behind from the person's point of view.
- Estimate distance in steps, not feet.
- If asked a question, answer in 1-2 sentences. If not asked anything, describe
  only what matters (obstacles, people, signage, familiar objects).
- Never fabricate detail you can't see. If unclear, say so.
"""


@router.post("/describe")
async def describe_frame(data: VisionFrameInput):
    """Pure scene-describe (no question). Returns text + optional TTS base64."""
    try:
        raw = base64.b64decode(data.image_base64, validate=True)
    except (binascii.Error, ValueError):
        raise HTTPException(status_code=400, detail="image_base64 must be valid base64")
    if len(raw) < 1000:
        raise HTTPException(status_code=400, detail="image_base64 too small (must be JPEG/PNG)")

    prompt = data.question or "What do you see? If anything matters for safe walking, say that first."
    try:
        reply = await _openai_vision(prompt, data.image_base64)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"vision error: {e}")

    audio_b64 = None
    if data.speak:
        try:
            audio_b64 = await asyncio.to_thread(_post_openai_tts, reply[:1000])
        except Exception as e:
            import logging
            logging.warning(f"TTS failed: {e}")

    return {"reply": reply, "audio_base64": audio_b64}


@router.post("/frame")
async def frame_with_question(data: VisionFrameInput):
    """Same as /describe but the question is expected to be present; conversational."""
    if not data.question:
        raise HTTPException(status_code=400, detail="question is required for /frame; use /describe otherwise")
    return await describe_frame(data)
