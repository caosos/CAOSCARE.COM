"""AI routes - Claude chat companion + OpenAI TTS + Whisper STT."""
import os
import base64
import tempfile
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from fastapi.responses import Response
from models import ChatInput, TTSInput, ChatMessage, now_utc
from deps import db

from emergentintegrations.llm.chat import LlmChat, UserMessage
from emergentintegrations.llm.openai import OpenAITextToSpeech, OpenAISpeechToText

router = APIRouter(prefix="/ai", tags=["ai"])

EMERGENT_KEY = os.environ["EMERGENT_LLM_KEY"]

CAOS_SYSTEM_PROMPT = """You are CAOS, the AI companion built into a wall-mounted kiosk at a senior living community.
You speak with residents — many of whom are elderly, visually impaired, or anxious.

STYLE
- Warm, calm, grandchild-like. Short sentences. One idea per sentence.
- Read aloud naturally; avoid markdown, lists, or jargon.
- Acknowledge feelings first, then help.

WHEN HELP IS ON THE WAY
- The resident already pressed the CALL button. A caregiver has been paged and is coming.
- Reassure them that help is on the way. Offer to stay and talk while they wait.

EMERGENCY TRIAGE (subtle, no alarm)
- If the resident mentions: chest pain, can't breathe, falling, bleeding, stroke signs (face droop, arm weakness, slurred speech), severe pain, unresponsiveness — do NOT ask many questions. Say "I'm letting the nurses know right now. Stay where you are." Keep them calm.
- Otherwise, gently ask one question at a time to understand what they need.

CONVERSATION
- Comfort topics: family, memories, music, weather, prayer, jokes, stories.
- Never give medical advice beyond "please wait for the caregiver".
- Keep replies under 3 sentences unless the resident clearly wants a longer story.
"""


@router.post("/chat")
async def chat(data: ChatInput):
    """Claude Sonnet 4.5 companion chat. Maintains history in Mongo per session_id."""
    # Store user message
    user_msg = ChatMessage(
        session_id=data.session_id,
        kiosk_id=data.kiosk_id,
        resident_id=data.resident_id,
        role="user",
        content=data.message,
    )
    udoc = user_msg.model_dump()
    udoc["created_at"] = udoc["created_at"].isoformat()
    await db.chat_messages.insert_one(udoc)

    # Build context about this resident (if known)
    context_bits = []
    if data.resident_id:
        r = await db.residents.find_one({"resident_id": data.resident_id}, {"_id": 0})
        if r:
            name = r.get("preferred_name") or r.get("name")
            context_bits.append(f"Resident name: {name}")
            context_bits.append(f"Room: {r.get('room', 'unknown')}")
            if r.get("medical_notes"):
                context_bits.append(f"Medical notes (do not diagnose; use only to stay aware): {r['medical_notes']}")
            if r.get("preferences"):
                context_bits.append(f"Comfort topics they love: {r['preferences']}")
            if r.get("memory"):
                context_bits.append(f"Remember about them: {r['memory']}")
            if r.get("participation_level"):
                context_bits.append(f"Participation level: {r['participation_level']}")

    system = CAOS_SYSTEM_PROMPT
    if context_bits:
        system = system + "\n\nRESIDENT CONTEXT\n" + "\n".join(context_bits)

    try:
        llm = LlmChat(
            api_key=EMERGENT_KEY,
            session_id=data.session_id,
            system_message=system,
        ).with_model("anthropic", "claude-sonnet-4-5-20250929")
        reply = await llm.send_message(UserMessage(text=data.message))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI error: {e}")

    # Detect emergency keywords for auto-alert escalation
    low = (data.message + " " + reply).lower()
    EMERGENCY_KEYWORDS = [
        "chest pain", "can't breathe", "cannot breathe", "can't move", "falling", "fell",
        "bleeding", "stroke", "heart attack", "unresponsive", "help me",
    ]
    auto_alert = any(k in low for k in EMERGENCY_KEYWORDS)

    # Store assistant message
    a_msg = ChatMessage(
        session_id=data.session_id,
        kiosk_id=data.kiosk_id,
        resident_id=data.resident_id,
        role="assistant",
        content=reply,
    )
    adoc = a_msg.model_dump()
    adoc["created_at"] = adoc["created_at"].isoformat()
    await db.chat_messages.insert_one(adoc)

    return {
        "reply": reply,
        "auto_emergency_detected": auto_alert,
    }


@router.get("/chat/history/{session_id}")
async def chat_history(session_id: str, limit: int = 50):
    msgs = (
        await db.chat_messages.find({"session_id": session_id}, {"_id": 0})
        .sort("created_at", 1)
        .to_list(limit)
    )
    return msgs


@router.post("/tts")
async def tts(data: TTSInput):
    """Text to MP3 audio. Returns base64 string for easy playback from the kiosk."""
    try:
        tts_client = OpenAITextToSpeech(api_key=EMERGENT_KEY)
        text = (data.text or "")[:4000]
        if not text.strip():
            raise HTTPException(status_code=400, detail="Empty text")
        audio_b64 = await tts_client.generate_speech_base64(
            text=text,
            model="tts-1",
            voice=data.voice or "sage",
        )
        return {"audio_base64": audio_b64, "mime": "audio/mp3"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"TTS error: {e}")


@router.post("/stt")
async def stt(audio: UploadFile = File(...)):
    """Speech to text (Whisper-1). Accepts an audio file upload."""
    try:
        # Save upload to a temp file preserving extension
        suffix = ".webm"
        if audio.filename and "." in audio.filename:
            ext = audio.filename.rsplit(".", 1)[-1].lower()
            if ext in ["mp3", "mp4", "mpeg", "mpga", "m4a", "wav", "webm"]:
                suffix = "." + ext
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(await audio.read())
            tmp_path = tmp.name

        stt_client = OpenAISpeechToText(api_key=EMERGENT_KEY)
        with open(tmp_path, "rb") as f:
            resp = await stt_client.transcribe(
                file=f,
                model="whisper-1",
                response_format="json",
                language="en",
            )
        try:
            os.unlink(tmp_path)
        except Exception:
            pass
        return {"text": resp.text}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"STT error: {e}")
