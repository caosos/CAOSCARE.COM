"""AI vision - Claude image understanding for glasses / camera devices.

The Android vision companion app (running on Vuzix M400 or any Android with a camera)
captures frames + audio, forwards them via BLE to the wall-mounted tablet (kiosk),
which POSTs them here. Claude describes the scene or answers the resident's spoken
question. TTS audio is generated and streamed back through the earbuds.
"""
import os
import base64
import binascii
from fastapi import APIRouter, HTTPException
from models import VisionFrameInput

from emergentintegrations.llm.chat import LlmChat, UserMessage, ImageContent
from emergentintegrations.llm.openai import OpenAITextToSpeech

router = APIRouter(prefix="/vision", tags=["vision"])
EMERGENT_KEY = os.environ["EMERGENT_LLM_KEY"]

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
    session = data.session_id or "caos-vision"
    try:
        llm = LlmChat(
            api_key=EMERGENT_KEY,
            session_id=session,
            system_message=VISION_SYSTEM_PROMPT,
        ).with_model("anthropic", "claude-sonnet-4-5-20250929")
        reply = await llm.send_message(
            UserMessage(
                text=prompt,
                image_contents=[ImageContent(image_base64=data.image_base64)],
            )
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"vision error: {e}")

    audio_b64 = None
    if data.speak:
        try:
            tts = OpenAITextToSpeech(api_key=EMERGENT_KEY)
            audio_b64 = await tts.generate_speech_base64(
                text=reply[:1000],
                model="tts-1",
                voice="sage",
            )
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
