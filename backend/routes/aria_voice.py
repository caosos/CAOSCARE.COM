"""Low-cost Aria voice, backend half (aria-low-cost-streaming-voice-001; docs/ARIA_LOW_COST_VOICE_PROTOTYPE.md).

The room page keeps Aria's handler, tools and memory; only the transport changes. This module is the part of
that transport that touches the provider, so the provider key, the receipts and the budget stay in the backend:
  speech -> text   POST /aria-voice/transcribe   gpt-4o-mini-transcribe   purpose speech_transcription
  text   -> reply  POST /aria-voice/respond      gpt-4o-mini, streamed    purpose = the session's purpose
  text   -> speech POST /aria-voice/speak      the kiosk picker's voice, streamed       purpose speech_generation
Instructions and tools are the ones the room session already builds (realtime_resident_session._mint); they are
stored here at session start and never accepted from the client. No Realtime model is used. Models and voice are
configuration (ARIA_VOICE_*); a different text provider only needs its own _stream().

Off unless ARIA_VOICE_CASCADE=1. ARIA_VOICE_DEFAULT_TRANSPORT (cascade|realtime) is the room page's default; the
kiosk's switch overrides it. Paid tests (CAOSCARE_PAID_TEST_BUDGET_ID set): each session first reserves its bounded
worst case against the owner-approved budget, fail closed. Live rooms: receipted, never blocked (as Realtime).
"""
import base64
import hashlib
import json
import os
import re
import secrets
from datetime import timedelta

import httpx
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from deps import db
from models import now_utc

router = APIRouter(prefix="/aria-voice", tags=["realtime"])

STT_MODEL = os.environ.get("ARIA_VOICE_STT_MODEL", "gpt-4o-mini-transcribe").strip()
TEXT_MODEL = os.environ.get("ARIA_VOICE_TEXT_MODEL", "gpt-4o-mini").strip()
# Speech: one model, the voice the room page's picker chose (Kiosk.jsx VOICES). Every voice costs the same.
TTS_MODEL = os.environ.get("ARIA_VOICE_TTS_MODEL", "gpt-4o-mini-tts").strip()
TTS_VOICES = {"alloy", "ash", "ballad", "coral", "echo", "fable", "nova", "onyx", "sage", "shimmer", "verse",
              "marin", "cedar"}
DEFAULT_VOICE = os.environ.get("ARIA_VOICE_DEFAULT_VOICE", "nova").strip()   # owner choice 2026-10-17
SPEED = float(os.environ.get("ARIA_VOICE_SPEED", "1.1"))   # owner 2026-10-17: "speed up the voice one notch"
FIXED_MAX_CHARS = 80   # fixed lines (greeting, routine goodbye) are cached; conversation audio never is
SPEECH_STYLE = ("Everyday conversational voice at a normal, lively pace - a friendly person chatting in the room. "
                "Bright and relaxed; not dramatic, not hushed or whispery, not slow, not a storyteller.")   # owner 2026-10-17
BOUNDS = dict(max_responses=16, max_audio_seconds=30, max_text_input_tokens=32000, max_output_tokens=250,
              max_session_seconds=900, max_speech_chars=1000)
FIXED_CACHE = os.path.expanduser(os.environ.get("ARIA_VOICE_FIXED_CACHE", "~/.cache/caoscare/aria_voice_fixed_lines"))
MAX_AUDIO_BYTES = BOUNDS["max_audio_seconds"] * 16000 * 2 + 1024    # 16 kHz mono PCM16 WAV
MAX_INPUT_CHARS = BOUNDS["max_text_input_tokens"] * 3               # conservative chars-per-token bound
_ROLES = {"user", "assistant", "tool"}


LIVE_IDLE_SECONDS = 1800   # a live session stays valid while it is used; idle this long and its token expires


def enabled() -> bool:
    return os.environ.get("ARIA_VOICE_CASCADE", "").strip() == "1"


def default_transport() -> str:
    t = os.environ.get("ARIA_VOICE_DEFAULT_TRANSPORT", "").strip().lower()
    return "cascade" if enabled() and t == "cascade" else "realtime"


@router.get("/config")
async def config():
    """What the room page may offer: whether the low-cost voice is available, and the room's default."""
    return {"cascade_enabled": enabled(), "default_transport": default_transport()}


def _base() -> str:
    return os.environ.get("OPENAI_API_BASE", "https://api.openai.com/v1").rstrip("/")


def _key() -> str:
    from routes.realtime import _require_openai_key
    return _require_openai_key()


def _sha(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _load_lexicon():
    """Spoken forms (one file: backend/aria_voice_lexicon.json), applied only to what is sent to speech."""
    path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "aria_voice_lexicon.json")
    with open(path) as f:
        lex = {k: v for k, v in json.load(f).items() if not k.startswith("_")}
    rx = re.compile(r"\b(" + "|".join(re.escape(k) for k in sorted(lex, key=len, reverse=True)) + r")\b", re.I)
    low = {k.lower(): v for k, v in lex.items()}
    return lambda text: rx.sub(lambda m: low[m.group(0).lower()], text)


spoken = _load_lexicon()


def wav_bytes(pcm: bytes, rate: int = 24000) -> bytes:
    import io
    import wave
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(rate); w.writeframes(pcm)
    return buf.getvalue()


def voice_or_default(voice) -> str:
    v = (voice or "").strip().lower()
    return v if v in TTS_VOICES else DEFAULT_VOICE


def chat_tools(realtime_tools: list) -> list:
    """Realtime function tools -> chat-completions tools (same names, descriptions and schemas)."""
    return [{"type": "function", "function": {k: t[k] for k in ("name", "description", "parameters") if k in t}}
            for t in realtime_tools or [] if t.get("type") == "function" and t.get("name")]


async def create_cascade_session(*, session_id, purpose, room, kiosk_id, instructions, tools, temperature,
                                 voice=None) -> dict:
    """Called by the room session builder instead of a Realtime mint when the page asks for transport=cascade."""
    if not enabled():
        raise HTTPException(status_code=404, detail="Low-cost voice prototype is not enabled.")
    tts_model, tts_voice = TTS_MODEL, voice_or_default(voice)
    reservation_id = await _reserve_paid_test(purpose, session_id, tts_model)
    token = secrets.token_urlsafe(32)
    expires = now_utc() + timedelta(seconds=BOUNDS["max_session_seconds"] if reservation_id else LIVE_IDLE_SECONDS)
    await db.aria_voice_sessions.insert_one({
        "token_sha256": _sha(token), "session_id": session_id, "purpose": purpose, "room": room,
        "kiosk_id": kiosk_id, "instructions": instructions, "tools": chat_tools(tools),
        "temperature": temperature, "reservation_id": reservation_id, "responses": 0,
        "tts_model": tts_model, "tts_voice": tts_voice, "spoken_chars": 0,
        "created_at": now_utc().isoformat(), "expires_at": expires.isoformat(), "ended_at": None})
    return {"transport": "cascade", "token": token, "expires_at": expires.isoformat(),
            "stt_model": STT_MODEL, "tts": f"{tts_model}:{tts_voice}", "audio_sample_rate": 24000,
            "session": {"model": TEXT_MODEL}}


async def _reserve_paid_test(purpose, session_id, tts_model):
    """Paid test: reserve the bounded worst case or refuse (fail closed). Live room: nothing to reserve."""
    import paid_api_ledger as L
    from routes.paid_api_receipts import ledger, test_budget_id
    budget_id = test_budget_id()
    if not budget_id:
        return None
    try:
        out = ledger().budget.reserve_cascade(budget_id, stt_model=STT_MODEL, text_model=TEXT_MODEL, tts_model=tts_model,
                                              provenance=L.provenance(purpose, session_id=session_id), **BOUNDS)
    except Exception as e:   # noqa: BLE001 - the guard fails closed
        raise HTTPException(status_code=503, detail=f"Low-cost voice refused: budget guard unavailable ({e})")
    if not out.get("ok"):
        raise HTTPException(status_code=503, detail=f"Low-cost voice refused: {out.get('reason')}")
    ledger().budget.bind_session(out["reservation_id"], session_id)
    return out["reservation_id"]


async def _session(request: Request) -> dict:
    token = request.headers.get("x-aria-voice-token") or ""
    s = await db.aria_voice_sessions.find_one({"token_sha256": _sha(token), "ended_at": None}) if token else None
    if not s or s["expires_at"] < now_utc().isoformat():
        raise HTTPException(status_code=401, detail="No live low-cost voice session.")
    if not s.get("reservation_id"):   # live: valid while in use
        await db.aria_voice_sessions.update_one({"_id": s["_id"]}, {"$set": {
            "expires_at": (now_utc() + timedelta(seconds=LIVE_IDLE_SECONDS)).isoformat()}})
    return s


@router.post("/transcribe")
async def transcribe(request: Request):
    s = await _session(request)
    audio = await request.body()
    if not audio or len(audio) > MAX_AUDIO_BYTES:
        raise HTTPException(status_code=413, detail="Speech segment missing or longer than the session bound.")
    from routes.paid_api_receipts import record_request_async, now_iso
    key, t0, r = _key(), now_iso(), None
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            r = await client.post(f"{_base()}/audio/transcriptions", headers={"Authorization": f"Bearer {key}"},
                                  data={"model": STT_MODEL, "response_format": "json"},   # no forced language, as the room session
                                  files={"file": ("speech.wav", audio, "audio/wav")})
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"Transcription unreachable ({type(e).__name__}).")
    finally:
        await record_request_async(r, purpose="speech_transcription", endpoint="audio/transcriptions",
                                   model_requested=STT_MODEL, started_at=t0, key=key, session_id=s["session_id"],
                                   conversation_purpose=s["purpose"], room=s["room"])
    if r.status_code >= 400:
        raise HTTPException(status_code=502, detail=f"Transcription returned HTTP {r.status_code}.")
    return {"text": (r.json().get("text") or "").strip()}


MAX_RESPONSE_INSTRUCTIONS = 4000


def _messages(s: dict, items, instructions=None) -> list:
    """Realtime semantics: a response's own `instructions` replace the session's for that one response."""
    if not isinstance(items, list):
        raise HTTPException(status_code=422, detail="items must be a list.")
    if instructions is not None and (not isinstance(instructions, str) or len(instructions) > MAX_RESPONSE_INSTRUCTIONS):
        raise HTTPException(status_code=422, detail="response instructions must be a short string.")
    msgs = [{"role": "system", "content": instructions or s["instructions"]}]
    for it in items:
        if not isinstance(it, dict) or it.get("role") not in _ROLES:
            raise HTTPException(status_code=422, detail="items may only carry user, assistant and tool turns.")
        msgs.append(it)
    if len(json.dumps(msgs)) + len(json.dumps(s["tools"])) > MAX_INPUT_CHARS:
        raise HTTPException(status_code=413, detail="Conversation is longer than the session's input bound.")
    return msgs


@router.post("/respond")
async def respond(request: Request, payload: dict):
    s = await _session(request)
    cap = {"responses": {"$lt": BOUNDS["max_responses"]}} if s.get("reservation_id") else {}   # paid tests only
    n = await db.aria_voice_sessions.find_one_and_update({"_id": s["_id"], **cap}, {"$inc": {"responses": 1}})
    if not n:
        raise HTTPException(status_code=429, detail="This session reached its response bound.")
    body = {"model": TEXT_MODEL, "messages": _messages(s, payload.get("items"), payload.get("instructions")),
            "stream": True, "stream_options": {"include_usage": True},
            "max_completion_tokens": BOUNDS["max_output_tokens"], "temperature": s.get("temperature") or 0.8}
    if s["tools"] and payload.get("tool_choice") != "none":
        body.update(tools=s["tools"], tool_choice="auto")
    return StreamingResponse(_stream(s, body), media_type="text/event-stream")


async def _stream(s: dict, body: dict):
    """Provider chunks -> {"type": text|tool_call|done|error} SSE events; one receipt with the final usage."""
    from routes.paid_api_receipts import record_request_async, now_iso
    key, t0, resp, summary, calls = _key(), now_iso(), None, {}, {}
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(30.0, connect=10.0)) as client:
            async with client.stream("POST", f"{_base()}/chat/completions", json=body,
                                     headers={"Authorization": f"Bearer {key}"}) as resp:
                if resp.status_code >= 400:
                    await resp.aread()
                    yield _sse({"type": "error", "status": resp.status_code})
                    return
                async for line in resp.aiter_lines():
                    if not line.startswith("data: ") or line == "data: [DONE]":
                        continue
                    chunk = json.loads(line[6:])
                    summary.update({k: chunk[k] for k in ("id", "model", "usage") if chunk.get(k)})
                    for ch in chunk.get("choices") or []:
                        d = ch.get("delta") or {}
                        if d.get("content"):
                            yield _sse({"type": "text", "delta": d["content"]})
                        for tc in d.get("tool_calls") or []:
                            c = calls.setdefault(tc.get("index", 0), {"id": None, "name": "", "arguments": ""})
                            f = tc.get("function") or {}
                            c["id"] = tc.get("id") or c["id"]
                            c["name"] += f.get("name") or ""
                            c["arguments"] += f.get("arguments") or ""
                        if ch.get("finish_reason"):
                            for c in calls.values():
                                yield _sse({"type": "tool_call", **c})
                            yield _sse({"type": "done", "finish_reason": ch["finish_reason"]})
    except httpx.HTTPError as e:
        yield _sse({"type": "error", "status": type(e).__name__})
    finally:
        await record_request_async(resp, purpose=s["purpose"], endpoint="chat/completions",
                                   model_requested=TEXT_MODEL, started_at=t0, key=key, session_id=s["session_id"],
                                   body=summary, room=s["room"], transport="cascade")


@router.post("/speak")
async def speak(request: Request, payload: dict):
    """One sentence of Aria's reply as raw PCM16 24 kHz mono, streamed as the provider produces it. A short line the
    page marks `fixed` (its greeting, the routine goodbye) is cached, so it plays with no provider request after
    its first use; conversation audio is never stored."""
    s = await _session(request)
    text = (payload.get("text") or "").strip()
    if not text or len(text) > BOUNDS["max_speech_chars"]:
        raise HTTPException(status_code=413, detail="Nothing to say, or longer than the session bound.")
    say = spoken(text)
    cache = None
    if payload.get("fixed") is True and len(say) <= FIXED_MAX_CHARS:
        cache = os.path.join(FIXED_CACHE, hashlib.sha256(
            f"{s['tts_model']}|{s['tts_voice']}|{SPEED}|{SPEECH_STYLE}|{say}".encode()).hexdigest() + ".pcm")
        if os.path.exists(cache):
            return StreamingResponse(_file(cache), media_type="audio/pcm")
    cap = ({"spoken_chars": {"$lte": BOUNDS["max_responses"] * BOUNDS["max_speech_chars"] - len(say)}}
           if s.get("reservation_id") else {})   # paid tests only
    n = await db.aria_voice_sessions.find_one_and_update({"_id": s["_id"], **cap}, {"$inc": {"spoken_chars": len(say)}})
    if not n:
        raise HTTPException(status_code=429, detail="This session reached its speech bound.")
    return StreamingResponse(_speech(s, say, cache), media_type="audio/pcm")


async def _file(path):
    with open(path, "rb") as f:
        yield f.read()


async def _speech(s: dict, say: str, cache):
    kept = []
    async for pcm in speech_stream(s["tts_model"], s["tts_voice"], say, session_id=s["session_id"],
                                   conversation_purpose=s["purpose"], room=s["room"], transport="cascade"):
        kept.append(pcm); yield pcm
    if cache and kept:
        os.makedirs(os.path.dirname(cache), exist_ok=True)
        with open(cache, "wb") as f:
            f.write(b"".join(kept))


async def speech_stream(model, voice, say, *, session_id=None, **where):
    """The one place Aria's speech is requested: PCM16 24 kHz chunks as the provider produces them, one receipt.
    tts-1 is billed per character (no usage in the response); gpt-4o-mini-tts reports usage over SSE."""
    from routes.paid_api_receipts import record_request_async, now_iso
    sse = model != "tts-1"
    body = {"model": model, "voice": voice, "input": say, "response_format": "pcm", "speed": SPEED}
    if sse:
        body.update(stream_format="sse", instructions=SPEECH_STYLE)
    key, t0, resp, summary = _key(), now_iso(), None, {}
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(30.0, connect=10.0)) as client:
            async with client.stream("POST", f"{_base()}/audio/speech", json=body,
                                     headers={"Authorization": f"Bearer {key}"}) as resp:
                if resp.status_code >= 400:
                    await resp.aread()
                    return
                if not sse:
                    async for chunk in resp.aiter_bytes():
                        yield chunk
                    return
                async for line in resp.aiter_lines():
                    if not line.startswith("data: ") or line.strip() == "data: [DONE]":
                        continue
                    ev = json.loads(line[6:])
                    if ev.get("type") == "speech.audio.delta":
                        yield base64.b64decode(ev.get("audio") or "")
                    elif ev.get("type") == "speech.audio.done":
                        summary = {"model": model, "usage": ev.get("usage")}
    except httpx.HTTPError:
        return
    finally:
        await record_request_async(resp, purpose="speech_generation", endpoint="audio/speech", model_requested=model,
                                   started_at=t0, key=key, session_id=session_id, body=summary,
                                   chars=None if summary.get("usage") else len(say), voice=voice, **where)


def _sse(obj: dict) -> str:
    return f"data: {json.dumps(obj)}\n\n"


@router.post("/end")
async def end(request: Request):
    s = await _session(request)
    await db.aria_voice_sessions.update_one({"_id": s["_id"]}, {"$set": {"ended_at": now_utc().isoformat()}})
    from routes.paid_api_receipts import ledger
    from routes.paid_api_receipts import _safe
    if s.get("reservation_id"):
        await _safe(ledger().budget.close, s["reservation_id"], "session_ended")
    return {"ok": True}
