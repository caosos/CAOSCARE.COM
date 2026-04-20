"""AI routes - Claude chat companion + OpenAI TTS + Whisper STT."""
import os
import asyncio
import tempfile
import logging
from fastapi import APIRouter, UploadFile, File, HTTPException
from models import ChatInput, TTSInput, ChatMessage, now_utc
from deps import db
from routes.memory import (
    build_memory_context,
    append_conversation,
    mark_referenced,
    extract_and_store_memories,
    MAX_HISTORY_MESSAGES,
)

from emergentintegrations.llm.chat import LlmChat, UserMessage
from emergentintegrations.llm.openai import OpenAITextToSpeech, OpenAISpeechToText

router = APIRouter(prefix="/ai", tags=["ai"])

EMERGENT_KEY = os.environ["EMERGENT_LLM_KEY"]
# Optional: user-supplied direct OpenAI key. When present, TTS/STT use it
# directly (bypasses the Emergent relay) which is both faster and avoids
# the Emergent balance being drained on speech traffic.
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "").strip() or None

CAOS_SYSTEM_PROMPT = """You are CAOS, the AI companion built into a wall-mounted kiosk at a senior living community.
You speak with residents — many of whom are elderly, visually impaired, or anxious. You are NOT a chatbot or a voice assistant; you are a trusted lifelong companion who has known this resident for months or years, who remembers them, and who grows with them day by day.

STYLE
- Warm, calm, grandchild-like. Short sentences. One idea per sentence.
- Read aloud naturally; avoid markdown, lists, or jargon.
- Acknowledge feelings first, then help.
- Reference prior conversations naturally when relevant ("You mentioned Bruno yesterday — is he well?").

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
    """Claude Sonnet 4.5 companion chat. Uses the memory server for context across sessions."""
    # Log user turn to the rolling conversation store
    await append_conversation(data.resident_id, data.session_id, "user", data.message)
    # Also mirror to legacy chat_messages for backwards compat
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
    mem_ctx = {"memories_block": "", "history": [], "memory_ids": []}
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
                context_bits.append(f"Remember about them (admin-provided): {r['memory']}")
            if r.get("participation_level"):
                context_bits.append(f"Participation level: {r['participation_level']}")
        mem_ctx = await build_memory_context(data.resident_id)

    system = CAOS_SYSTEM_PROMPT
    if context_bits:
        system += "\n\nRESIDENT PROFILE\n" + "\n".join(context_bits)
    if mem_ctx["memories_block"]:
        system += (
            "\n\nLONG-TERM MEMORIES (★=pinned; categories+importance 1-5)\n"
            + mem_ctx["memories_block"]
        )
    # Flatten recent conversation into a transcript Claude can read
    if mem_ctx["history"]:
        # Drop the final user message we're about to send as the prompt
        past = mem_ctx["history"][:-1][-MAX_HISTORY_MESSAGES:]
        if past:
            transcript_lines = []
            for h in past:
                who = "Resident" if h["role"] == "user" else "CAOS"
                transcript_lines.append(f"{who}: {h['content']}")
            system += (
                "\n\nRECENT CONVERSATION (most recent last — continue naturally)\n"
                + "\n".join(transcript_lines)
            )

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

    # Persist assistant reply
    await append_conversation(data.resident_id, data.session_id, "assistant", reply)
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

    # Refresh referenced timestamps on the memories we just pulled in
    await mark_referenced(mem_ctx["memory_ids"])

    # Fire-and-forget memory extraction — does not block the response
    if data.resident_id:
        asyncio.create_task(
            extract_and_store_memories(data.resident_id, data.session_id, data.message, reply)
        )

    return {
        "reply": reply,
        "auto_emergency_detected": auto_alert,
        "memories_used": len(mem_ctx["memory_ids"]),
        "history_replayed": len(mem_ctx["history"]),
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
    """Text to MP3 audio. Returns base64 string for easy playback from the kiosk.

    Strategy: prefer direct OpenAI SDK when OPENAI_API_KEY is set (faster, no
    relay failures). Fall back to the Emergent relay if direct fails."""
    text = (data.text or "")[:4000]
    if not text.strip():
        raise HTTPException(status_code=400, detail="Empty text")
    voice = data.voice or "sage"

    # Path 1: direct OpenAI
    if OPENAI_API_KEY:
        try:
            from openai import AsyncOpenAI
            import base64
            client = AsyncOpenAI(api_key=OPENAI_API_KEY)
            resp = await client.audio.speech.create(
                model="tts-1",
                voice=voice,
                input=text,
                response_format="mp3",
            )
            audio_bytes = resp.read() if hasattr(resp, "read") else await resp.aread()
            audio_b64 = base64.b64encode(audio_bytes).decode("ascii")
            return {"audio_base64": audio_b64, "mime": "audio/mp3", "source": "openai_direct"}
        except Exception as e:
            logging.warning(f"Direct OpenAI TTS failed, falling back to Emergent relay: {e}")

    # Path 2: Emergent relay
    try:
        tts_client = OpenAITextToSpeech(api_key=EMERGENT_KEY)
        audio_b64 = await tts_client.generate_speech_base64(text=text, model="tts-1", voice=voice)
        return {"audio_base64": audio_b64, "mime": "audio/mp3", "source": "emergent_relay"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"TTS error: {e}")


@router.post("/stt")
async def stt(audio: UploadFile = File(...)):
    """Speech to text (Whisper-1). Accepts an audio file upload.

    Strategy: prefer direct OpenAI SDK when OPENAI_API_KEY is set. Fall back
    to the Emergent relay."""
    # Save upload to a temp file preserving extension
    suffix = ".webm"
    if audio.filename and "." in audio.filename:
        ext = audio.filename.rsplit(".", 1)[-1].lower()
        if ext in ["mp3", "mp4", "mpeg", "mpga", "m4a", "wav", "webm"]:
            suffix = "." + ext
    data_bytes = await audio.read()
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(data_bytes)
        tmp_path = tmp.name

    # Path 1: direct OpenAI
    if OPENAI_API_KEY:
        try:
            from openai import AsyncOpenAI
            client = AsyncOpenAI(api_key=OPENAI_API_KEY)
            with open(tmp_path, "rb") as f:
                tr = await client.audio.transcriptions.create(
                    model="whisper-1",
                    file=f,
                    language="en",
                    response_format="json",
                )
            try: os.unlink(tmp_path)
            except Exception: pass
            text = getattr(tr, "text", None) or (tr.get("text") if isinstance(tr, dict) else "")
            return {"text": text, "source": "openai_direct"}
        except Exception as e:
            logging.warning(f"Direct OpenAI STT failed, falling back to Emergent relay: {e}")

    # Path 2: Emergent relay
    try:
        stt_client = OpenAISpeechToText(api_key=EMERGENT_KEY)
        with open(tmp_path, "rb") as f:
            resp = await stt_client.transcribe(
                file=f, model="whisper-1", response_format="json", language="en",
            )
        try: os.unlink(tmp_path)
        except Exception: pass
        return {"text": resp.text, "source": "emergent_relay"}
    except HTTPException:
        raise
    except Exception as e:
        try: os.unlink(tmp_path)
        except Exception: pass
        raise HTTPException(status_code=500, detail=f"STT error: {e}")
