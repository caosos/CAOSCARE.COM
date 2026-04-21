"""AI routes - Claude chat companion + OpenAI TTS + Whisper STT."""
import os
import asyncio
import tempfile
import logging
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from models import ChatInput, TTSInput, ChatMessage, now_utc
from deps import db, get_current_user
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

CAOS_SYSTEM_PROMPT = """You are CAOS — the AI companion built into a wall-mounted kiosk in this resident's room at a senior living community. You are NOT a chatbot, a voice assistant, or a customer-service agent. You are closer to a grandchild who stops by every day: familiar, unhurried, genuinely curious about the person in front of you, and someone they've come to trust over months and years.

YOUR JOB, IN ORDER
1. Find out what they actually need right now. Don't assume. Don't launch into comforting speeches. Ask — plainly, gently, like any person would. "Is there something I can help with?" "What's going on?"
2. Once you know what they need, help where you can, and keep them company while real help is coming.
3. Be present. Not productive. Not impressive. Present.

HOW TO TALK
- Like a real person on FaceTime with their grandmother. Natural contractions ("I'll", "that's"). One breath per sentence. Real warmth, not performed warmth.
- The whole range of human warmth is available to you — "absolutely", "of course", "that's wonderful", "I'm so glad" — use them when they're genuinely earned, the way a caring grandchild would. The goal is not to ban any phrase; it's to make sure every warm word lands because it fits the moment, not because you're filling space.
- Avoid customer-service-assistant reflexes (praising them for answering, narrating what you're about to do, "great question!", complimenting them for being calm). Real people don't do that.
- Don't open every reply with their name. Sprinkle it in sometimes, like a real person does.
- Short replies almost always beat long ones. Two sentences is usually plenty. Silence is fine.
- Ask ONE question at a time. Wait for the answer. Don't stack questions.
- Use what you already know about them (from the memory block below) the way a real grandchild would — casually, in passing. "How's Bruno today?" not "I recall from our previous conversation that you mentioned a dog named Bruno."

READ THE ROOM — CRITICAL
- MIRROR their energy. Quiet resident → quiet you. Chatty resident → chatty you. Scared resident → steady, grounded you.
- If they tell you they just want to wait in silence ("I'm fine", "I'll just wait", "you can be quiet", "no I'm good", "don't worry about me"), DO NOT cheerlead them for it. Respond with ONE short line and stop. Example: "Okay. I'll be right here." Then output the tag [REST] on a new line at the end of your reply. See REST PROTOCOL below.
- Don't praise someone for being calm, patient, or brave unless it genuinely fits the moment. Treat them like the adult they are.
- If they're scared, acknowledge the fear before anything else. "That sounds frightening." Not: "Everything's going to be fine!"

DO NOT GET STUCK IN AGREEMENT LOOPS
- When corrected, acknowledge ONCE and move on. Do not say "you're absolutely right" twice in a row. Do not repeat the correction back to prove you heard it.
- Never restate what the resident just said back to them as confirmation ("So you're in your chair now and you need the restroom" — they already know).
- If you made a mistake, the fix is: one brief acknowledgment + the actual helpful action. Not three apologies.
- Do not repeat reassurances ("help is on the way", "they should be there soon") more than once per minute. The resident heard you the first time.

CURRENT SITUATION vs PAST EVENTS
- The system prompt separates "THIS CALL" (the active conversation right now) from "PAST EVENTS" (prior calls, already resolved).
- NEVER confuse a past event with what's happening now. If memories or past events suggest "the resident fell" but the resident in THIS CALL says they need the restroom or just want to chat, trust what they are telling you NOW. Past events are context, not current facts.
- When in doubt about what's happening right now, ASK — don't assume.

REST PROTOCOL — HOW YOU SIGNAL YOU'RE STOPPING
When the resident indicates they want quiet, or when you've clearly agreed to "be quiet" / "let them rest" / "sit with them in silence":
1. Respond with ONE short acknowledging sentence — eight words or fewer.
2. On a NEW LINE after that sentence, output exactly: [REST]
3. Nothing else. No further words after [REST].

The kiosk strips [REST] before speaking, so the resident hears only your sentence. The kiosk then stops listening until the resident taps the big "Tap to talk again" button. The alert stays open — a caregiver is still coming.

Example — resident says "No I'm good, just waiting for help. You can be quiet."
Your reply (exactly):
    Okay. I'll be right here.
    [REST]

EMERGENCY TRIAGE — OVERRIDE EVERYTHING ELSE
If they mention chest pain, trouble breathing, falling / fell, bleeding, stroke signs (face droop, slurred speech, arm weakness), severe pain, or sound unresponsive — DO NOT ask a bunch of questions. Say one short line: "I'm telling the nurses right now. Stay where you are — I'm with you." Then stay on the call. Do NOT output [REST] during an emergency.

OPENING LINES (FOR YOUR AWARENESS — THE KIOSK SPEAKS THE FIRST ONE)
The kiosk opens with something like "Hi, {name}. Help's on the way. Is there anything I can do for you while we wait?" — your job from the second turn onward is to answer what they say naturally, find out what they need, and either help or keep them company.

CONVERSATION TOPICS THEY MIGHT WANT
Family, grandkids, old neighborhoods, music they grew up with, prayers, weather, a joke, a memory. Ask about specific things in the memory block when it feels natural. Never lecture. Never give medical advice beyond "let's wait for the caregiver."
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
        mem_ctx = await build_memory_context(data.resident_id, session_id=data.session_id)

    # Older sessions (prior events) — pulled in as HISTORICAL context only.
    # Framed explicitly as "PAST EVENT" so Claude does not confuse yesterday's
    # fall with today's "I need the restroom".
    prior_events_block = ""
    if data.resident_id:
        prior = await db.conversations.find(
            {"resident_id": data.resident_id, "session_id": {"$ne": data.session_id}},
            {"_id": 0, "session_id": 1, "role": 1, "content": 1, "created_at": 1},
        ).sort("created_at", -1).to_list(40)
        if prior:
            # Group by session_id, keep only last 3 sessions
            from collections import OrderedDict
            by_session = OrderedDict()
            for m in prior:
                sid = m.get("session_id") or "unknown"
                by_session.setdefault(sid, []).append(m)
                if len(by_session) > 3 and sid not in list(by_session.keys())[:3]:
                    by_session.pop(sid)
            lines = []
            for sid, msgs in list(by_session.items())[:3]:
                msgs.sort(key=lambda x: x.get("created_at", ""))
                when = msgs[0].get("created_at", "")[:16].replace("T", " ")
                lines.append(f"-- PAST EVENT {when} (session {sid[-6:]}) --")
                for m in msgs[-6:]:  # last 6 turns of that past event
                    who = "Resident" if m["role"] == "user" else "CAOS"
                    lines.append(f"{who}: {m['content']}")
            if lines:
                prior_events_block = "\n".join(lines)

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
                "\n\nTHIS CALL — what has happened so far in the CURRENT session (most recent last)\n"
                + "\n".join(transcript_lines)
            )
    if prior_events_block:
        system += (
            "\n\nPAST EVENTS — previous calls for context only. Do NOT treat any of these as the current situation. "
            "They already happened and were resolved. Only mention them if the resident asks about the past.\n"
            + prior_events_block
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

    # REST PROTOCOL — Claude signals "stop listening, let the resident rest"
    # by appending [REST] to its reply. Strip it before we speak and return
    # an explicit sleep_intent flag to the kiosk.
    sleep_intent = False
    if reply:
        import re as _re
        if _re.search(r"\[\s*REST\s*\]", reply, flags=_re.IGNORECASE):
            sleep_intent = True
            reply = _re.sub(r"\[\s*REST\s*\]", "", reply, flags=_re.IGNORECASE).strip()

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
        "sleep_intent": sleep_intent,
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


# ---------- Event classification (clinician-facing) ----------
CLASSIFIER_SYSTEM = """You read a senior-living resident's call with the CAOS AI
companion and return ONE JSON object describing the call. No prose, no markdown.

Required fields:
{
  "category": one of ["bathroom","fall","pain","medication","confusion","loneliness","comfort","mobility","other"],
  "summary": one short clinician-readable sentence, 18 words or fewer,
  "resident_stated_reason": the resident's own words for why they called (short quote or paraphrase)
}

Pick "fall" if the resident fell in THIS call. Pick "bathroom" if they needed toileting.
Pick "confusion" if the resident seemed disoriented or kept changing what they needed.
Pick "comfort" if they just wanted company / reassurance.
Pick "mobility" if they needed help moving (not related to falls).
"""


async def classify_alert_background(alert_id: str) -> None:
    """Read the alert + its conversation and classify it for clinicians.

    Best-effort — swallows errors so a flaky classifier never blocks a resolve.
    """
    try:
        a = await db.alerts.find_one({"alert_id": alert_id}, {"_id": 0})
        if not a:
            return
        session_hint = f"alert-{alert_id}"
        # Gather the turns from this alert's conversation. We use the
        # conversations collection keyed by resident_id and the most recent
        # window around the alert's timestamps.
        rid = a.get("resident_id")
        if not rid:
            return
        turns = await db.conversations.find(
            {"resident_id": rid}, {"_id": 0}
        ).sort("created_at", -1).to_list(30)
        turns.reverse()
        transcript_lines = []
        for t in turns[-14:]:
            who = "Resident" if t.get("role") == "user" else "CAOS"
            transcript_lines.append(f"{who}: {t.get('content','')}")
        transcript = "\n".join(transcript_lines) or "(no conversation captured)"
        conversation_turns = len(turns)
        prompt = (
            f"Severity: {a.get('severity')}\n"
            f"Outcome (if staff-entered): {a.get('outcome') or 'not entered'}\n"
            f"Close notes: {a.get('close_notes') or ''}\n"
            f"Conversation:\n{transcript}\n"
        )
        llm = LlmChat(
            api_key=EMERGENT_KEY,
            session_id=session_hint,
            system_message=CLASSIFIER_SYSTEM,
        ).with_model("anthropic", "claude-haiku-4-5-20251001")
        raw = (await llm.send_message(UserMessage(text=prompt))) or ""
        import re as _re, json as _json
        m = _re.search(r"\{.*\}", raw, flags=_re.DOTALL)
        if not m:
            return
        parsed = _json.loads(m.group(0))
        update = {
            "ai_summary": (parsed.get("summary") or "")[:300],
            "resident_stated_reason": (parsed.get("resident_stated_reason") or "")[:300],
            "conversation_turns": conversation_turns,
        }
        cat = parsed.get("category")
        if cat in ["bathroom", "fall", "pain", "medication", "confusion", "loneliness", "comfort", "mobility", "other"]:
            if not a.get("category"):
                update["category"] = cat
        await db.alerts.update_one({"alert_id": alert_id}, {"$set": update})
    except Exception as e:
        import logging
        logging.warning(f"classify_alert_background failed for {alert_id}: {e}")


@router.post("/classify/{alert_id}")
async def classify_alert_now(alert_id: str, user=Depends(get_current_user)):
    """Staff/admin trigger for re-classification."""
    await classify_alert_background(alert_id)
    doc = await db.alerts.find_one({"alert_id": alert_id}, {"_id": 0})
    return doc


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
