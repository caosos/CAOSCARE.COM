"""Low-cost Aria voice, backend half (aria-low-cost-streaming-voice-001; docs/ARIA_LOW_COST_VOICE_PROTOTYPE.md).

The room page keeps Aria's handler, tools and memory; only the transport changes. This module is the part of
that transport that touches the provider, so the provider key, the receipts and the budget stay in the backend:
  speech -> text   POST /aria-voice/transcribe   gpt-4o-mini-transcribe   purpose speech_transcription
  text   -> reply  POST /aria-voice/respond      gpt-4o-mini, streamed    purpose = the session's purpose
Instructions and tools are the ones the room session already builds (realtime_resident_session._mint); they are
stored here at session start and never accepted from the client. No Realtime model is used.

Prototype only: off unless ARIA_VOICE_CASCADE=1, and every session needs an open owner-approved paid-test budget
(CAOSCARE_PAID_TEST_BUDGET_ID) that accepts its worst case first - fail closed.
"""
import hashlib
import json
import os
import secrets
from datetime import timedelta

import httpx
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from deps import db
from models import now_utc

router = APIRouter(prefix="/aria-voice", tags=["realtime"])

STT_MODEL = "gpt-4o-mini-transcribe"
TEXT_MODEL = "gpt-4o-mini"
BOUNDS = dict(max_responses=40, max_audio_seconds=30, max_text_input_tokens=32000, max_output_tokens=400,
              max_session_seconds=900)
MAX_AUDIO_BYTES = BOUNDS["max_audio_seconds"] * 16000 * 2 + 1024    # 16 kHz mono PCM16 WAV
MAX_INPUT_CHARS = BOUNDS["max_text_input_tokens"] * 3               # conservative chars-per-token bound
_ROLES = {"user", "assistant", "tool"}


def enabled() -> bool:
    return os.environ.get("ARIA_VOICE_CASCADE", "").strip() == "1"


def _base() -> str:
    return os.environ.get("OPENAI_API_BASE", "https://api.openai.com/v1").rstrip("/")


def _key() -> str:
    from routes.realtime import _require_openai_key
    return _require_openai_key()


def _sha(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def chat_tools(realtime_tools: list) -> list:
    """Realtime function tools -> chat-completions tools (same names, descriptions and schemas)."""
    return [{"type": "function", "function": {k: t[k] for k in ("name", "description", "parameters") if k in t}}
            for t in realtime_tools or [] if t.get("type") == "function" and t.get("name")]


async def create_cascade_session(*, session_id, purpose, room, kiosk_id, instructions, tools, temperature) -> dict:
    """Called by the room session builder instead of a Realtime mint when the page asks for transport=cascade."""
    if not enabled():
        raise HTTPException(status_code=404, detail="Low-cost voice prototype is not enabled.")
    import paid_api_ledger as L
    from routes.paid_api_receipts import ledger, test_budget_id
    budget_id = test_budget_id()
    if not budget_id:
        raise HTTPException(status_code=503, detail="Low-cost voice refused: no owner-approved paid-test budget.")
    try:
        out = ledger().budget.reserve_cascade(budget_id, stt_model=STT_MODEL, text_model=TEXT_MODEL,
                                              provenance=L.provenance(purpose, session_id=session_id), **BOUNDS)
    except Exception as e:   # noqa: BLE001 - the guard fails closed
        raise HTTPException(status_code=503, detail=f"Low-cost voice refused: budget guard unavailable ({e})")
    if not out.get("ok"):
        raise HTTPException(status_code=503, detail=f"Low-cost voice refused: {out.get('reason')}")
    ledger().budget.bind_session(out["reservation_id"], session_id)
    token = secrets.token_urlsafe(32)
    expires = now_utc() + timedelta(seconds=BOUNDS["max_session_seconds"])
    await db.aria_voice_sessions.insert_one({
        "token_sha256": _sha(token), "session_id": session_id, "purpose": purpose, "room": room,
        "kiosk_id": kiosk_id, "instructions": instructions, "tools": chat_tools(tools),
        "temperature": temperature, "reservation_id": out["reservation_id"], "responses": 0,
        "created_at": now_utc().isoformat(), "expires_at": expires.isoformat(), "ended_at": None})
    return {"transport": "cascade", "token": token, "expires_at": expires.isoformat(),
            "stt_model": STT_MODEL, "session": {"model": TEXT_MODEL}}


async def _session(request: Request) -> dict:
    token = request.headers.get("x-aria-voice-token") or ""
    s = await db.aria_voice_sessions.find_one({"token_sha256": _sha(token), "ended_at": None}) if token else None
    if not s or s["expires_at"] < now_utc().isoformat():
        raise HTTPException(status_code=401, detail="No live low-cost voice session.")
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
    n = await db.aria_voice_sessions.find_one_and_update(
        {"_id": s["_id"], "responses": {"$lt": BOUNDS["max_responses"]}}, {"$inc": {"responses": 1}})
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


def _sse(obj: dict) -> str:
    return f"data: {json.dumps(obj)}\n\n"


@router.post("/end")
async def end(request: Request):
    s = await _session(request)
    await db.aria_voice_sessions.update_one({"_id": s["_id"]}, {"$set": {"ended_at": now_utc().isoformat()}})
    from routes.paid_api_receipts import ledger
    from routes.paid_api_receipts import _safe
    await _safe(ledger().budget.close, s["reservation_id"], "session_ended")
    return {"ok": True}
