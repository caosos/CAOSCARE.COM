"""Voice bridge: one resident conversation turn as text.

For the Home Assistant conversation agent (Voice PE -> HA wake word +
speech-to-text -> this endpoint -> reply text -> HA text-to-speech). This is
HA's staged path, not the browser's realtime speech-to-speech session.

CAOSCare owns the conversation: the speaker's room comes from the voice
device's registered room endpoint (voice_bridge_session.resolve_identity),
turns go to the same conversation store as realtime calls, the instructions
are the same resident instructions the realtime mint builds, and every
action runs through the canonical services (voice_bridge_tools.py). HA holds
no resident or workflow data. Every turn - served, ended, duplicated,
failed or refused - leaves a receipt (voice_bridge_receipts.py).

Auth: a shared bridge credential (CAOSCARE_VOICE_BRIDGE_TOKEN) proves the
caller is the configured HA integration; the speaker is still an unverified
room claim, exactly as for the room screen and Aria voice.
"""
import asyncio
import hmac
from concurrent.futures import ThreadPoolExecutor
import json
import os
import random
import re
import time
import uuid
from typing import Optional

from fastapi import APIRouter, Header, HTTPException, Response
from pydantic import BaseModel

from deps import db
from routes.ai import _post_openai
from routes.arrival_claim_guard import candidate_tasks, guard_reply
from routes.realtime_diagnostics import DiagnosticEvent, log_event
from routes.realtime_memory_ingest import RealtimeTurnIngest, realtime_turn_ingest
from routes.resident_conversation_context import build_resident_instructions
from routes.capacity_telemetry import RECORDER
from routes.voice_bridge_admission import ADMISSION, CLASS_NAMES, MAX_WAIT_S, classify
from routes.voice_bridge_config import resolve_model
from routes.voice_bridge_receipts import refusal_receipt, turn_receipt
from routes.voice_bridge_session import (claim_turn, ending_phrase, open_or_get_session,
                                         record_turn, resolve_identity, session_state)
from routes.voice_bridge_tools import ENDING_TOOLS, bridge_tool_schemas, run_bridge_tool

router = APIRouter(prefix="/voice-bridge", tags=["voice-bridge"])
# The provider client is blocking (requests). It gets its own threads, one per
# admission slot, instead of asyncio's shared default pool (min(32, cpus+4)
# threads - 12 on the EliteDesk), which load tests showed capping concurrent
# model calls below the configured slots.
PROVIDER_POOL = ThreadPoolExecutor(max_workers=ADMISSION.max_active, thread_name_prefix="voice-bridge-llm")

MAX_TOOL_ROUNDS = 4
HISTORY_TURNS = 20
TURN_BUDGET_SECONDS = float(os.environ.get("CAOSCARE_VOICE_BRIDGE_BUDGET_S", "18"))
MODEL_CONFIG = resolve_model()  # read once at import; logged at startup (server.py)
CHANNEL_NOTE = (
    "\n\n## This conversation's channel\n"
    "You are speaking through the room's voice satellite: the resident's words "
    "reach you as text from speech recognition and your reply is read aloud. "
    "Reply in one to three short spoken sentences, no lists, no markup.\n"
)
FAILURE_REPLY = ("I'm having trouble right now. If you need help, please press your "
                 "call button or ask again in a moment.")
DEFERRED_REPLY = ("I'm helping a lot of people right now and couldn't do that yet. Please ask me "
                  "again in a minute. If you need help now, say 'I need help' or press your call button.")
EMERGENCY_REPLY = {"paged": "A nurse has been paged. I'm right here with you.",
                   "sent": "I've sent this to the care team as an emergency. I'm right here with you."}
EMERGENCY_FAILED = ("I couldn't reach the care team just now. Please press your call button. "
                    "I'm right here with you.")
FAILURE_AFTER_REQUEST = ("I've passed your request to the staff. I'm having trouble talking "
                         "right now, so I'll stop here.")


class VoiceBridgeTurn(BaseModel):
    device_id: Optional[str] = None       # HA device id of the voice endpoint
    satellite_id: Optional[str] = None    # HA assist satellite entity id, if HA sends one
    text: str
    conversation_id: Optional[str] = None
    language: Optional[str] = None


def _check_token(authorization: Optional[str]):
    expected = os.environ.get("CAOSCARE_VOICE_BRIDGE_TOKEN", "")
    if not expected:
        raise HTTPException(503, "voice bridge is not configured")
    given = (authorization or "").removeprefix("Bearer ").strip()
    if not hmac.compare_digest(given, expected):
        raise HTTPException(401, "invalid bridge credential")


def _session_id(conversation_id: Optional[str]) -> str:
    raw = re.sub(r"[^A-Za-z0-9_-]", "", conversation_id or "")[:64]
    return f"vb_{raw or uuid.uuid4().hex[:16]}"


def speakable(text: str) -> str:
    """Plain text for TTS and for display when TTS is unavailable."""
    t = re.sub(r"https?://\S+", "", text or "")
    t = re.sub(r"[*_#`>|~\[\]]", "", t)
    t = re.sub(r"^\s*[-•]\s+", "", t, flags=re.M)
    return re.sub(r"\s+", " ", t).strip()


async def _log(session_id: str, room: str, event_type: str, meta: dict):
    try:
        await log_event(DiagnosticEvent(session_id=session_id, event_type=event_type, room=room, meta=meta))
    except Exception:
        pass  # diagnostics never block a turn


async def _history(session_id: str) -> list:
    turns = await db.conversations.find(
        {"session_id": session_id}, {"_id": 0, "role": 1, "content": 1},
    ).sort("created_at", -1).to_list(HISTORY_TURNS)
    return [{"role": t["role"], "content": t["content"]} for t in reversed(turns)
            if t.get("role") in ("user", "assistant") and t.get("content")]


async def _ingest(ident: dict, session_id: str, role: str, text: str):
    await realtime_turn_ingest(RealtimeTurnIngest(
        resident_id=ident["resident_id"], session_id=session_id, role=role, text=text,
        room=ident["room"], kiosk_id=ident["kiosk_id"]))


def _rate_limited(e: Exception) -> bool:
    t = str(getattr(e, "detail", "") or e).lower()
    return "429" in t or "rate limit" in t or "rate_limit" in t


async def _provider_call(payload: dict, deadline: float) -> dict:
    """One model call; a rate-limit refusal is retried once after a short,
    jittered pause when the turn budget still allows a full call."""
    loop = asyncio.get_running_loop()
    for attempt in (1, 2):
        remaining = deadline - time.monotonic()
        try:
            return await loop.run_in_executor(
                PROVIDER_POOL, lambda: _post_openai("/chat/completions", payload, timeout=max(1, int(remaining))))
        except Exception as e:
            pause = 0.5 + random.random()
            if attempt == 2 or not _rate_limited(e) or deadline - time.monotonic() - pause < 4:
                raise
            await asyncio.sleep(pause)


async def _converse(ident: dict, session_id: str, text: str, budget: float = TURN_BUDGET_SECONDS) -> dict:
    """The model/tool loop. Tools run to completion once started (never
    cancelled mid-write); the time budget only stops further model calls."""
    ctx_payload = {"resident_id": ident["resident_id"], "room": ident["room"], "session_id": session_id}
    built = await build_resident_instructions(ctx_payload)
    messages = [{"role": "system", "content": built["instructions"] + CHANNEL_NOTE}]
    messages += await _history(session_id)
    tools = await bridge_tool_schemas()
    tool_ctx = {**ctx_payload, "last_user_text": text, "kiosk_id": ident["kiosk_id"],
                "origin_authority": f"registered_endpoint:{ident['kiosk_id']}"}
    used, results, ended, reply, error = [], [], False, "", None
    deadline = time.monotonic() + budget
    for _ in range(MAX_TOOL_ROUNDS + 1):
        remaining = deadline - time.monotonic()
        if remaining < 1:
            error = "turn time budget exhausted"
            break
        try:
            payload = {"model": MODEL_CONFIG["model"], "messages": messages, "tools": tools, "tool_choice": "auto"}
            resp = await _provider_call(payload, deadline)
            msg = resp["choices"][0]["message"]
        except Exception as e:  # provider down, timeout, malformed reply
            error = f"language model unavailable: {type(e).__name__}: {str(e)[:200]}"
            break
        calls = msg.get("tool_calls") or []
        if not calls:
            reply = (msg.get("content") or "").strip()
            break
        messages.append({"role": "assistant", "content": msg.get("content"), "tool_calls": calls})
        for call in calls:
            name = call["function"]["name"]
            try:
                args = json.loads(call["function"].get("arguments") or "{}")
            except ValueError:
                args = {}
            await _log(session_id, ident["room"], "tool_call", {"name": name, "args": args, "channel": "voice_bridge"})
            result = await run_bridge_tool(name, args, tool_ctx)
            await _log(session_id, ident["room"], "tool_result", {"name": name, "result": result})
            used.append({"name": name, "ok": bool(result.get("ok"))})
            results.append((name, result))
            ended = ended or (name in ENDING_TOOLS and bool(result.get("ok")))
            messages.append({"role": "tool", "tool_call_id": call["id"],
                             "content": json.dumps(result, default=str)})
    if not reply and not error:
        error = "no reply after tool rounds"
    if error:
        sent = any(n == "request_staff_help" and r.get("ok") for n, r in results)
        reply = FAILURE_AFTER_REQUEST if sent else FAILURE_REPLY
    else:
        reply, removed = await guard_reply(reply, await candidate_tasks([r for _, r in results], ident["resident_id"]))
        if removed:
            await _log(session_id, ident["room"], "reply_guarded",
                       {"removed": removed, "reason": "arrival_claim_without_claim_receipt"})
    return {"reply": speakable(reply) or FAILURE_REPLY, "tools": used, "results": results,
            "ended": ended, "error": error}


def _out(reply: str, conv_id: str, session_id: str, keep_open: bool, tools: list, receipt_id: str,
         **extra) -> dict:
    return {"response_text": reply, "speech_format": "plain_text", "conversation_id": conv_id,
            "session_id": session_id, "continue_conversation": keep_open,
            "tools_used": [t["name"] for t in tools], "receipt_id": receipt_id, **extra}


@router.post("/turn")
async def voice_bridge_turn(data: VoiceBridgeTurn, authorization: Optional[str] = Header(None),
                            response: Response = None):
    """Every turn is also counted for capacity monitoring (real vs simulated,
    priority class, outcome, latency)."""
    meta, t0, out = {}, time.monotonic(), None
    try:
        out = await _handle_turn(data, authorization, meta)
        return out
    finally:
        if "simulated" in meta:
            if response is not None and meta["simulated"]:
                response.headers["X-CAOSCare-Simulated"] = "1"
            o = out or {}
            outcome = ("emergency" if o.get("priority_class") == "emergency" else "deferred" if o.get("deferred")
                       else "duplicate" if o.get("duplicate") else "ended" if o.get("session_ended")
                       else "degraded" if o.get("degraded") else "served" if out else "error")
            RECORDER.voice_turn(o.get("priority_class") or "unclassified", outcome, time.monotonic() - t0,
                                meta["simulated"], meta.get("error"))


async def _handle_turn(data: VoiceBridgeTurn, authorization: Optional[str], meta: dict) -> dict:
    _check_token(authorization)
    if not MODEL_CONFIG["ok"]:
        raise HTTPException(503, MODEL_CONFIG["error"])
    text = (data.text or "").strip()
    if not text:
        raise HTTPException(422, "empty transcript")
    conv_id = data.conversation_id or uuid.uuid4().hex[:16]
    device_ids = [data.device_id, data.satellite_id]
    try:
        ident = await resolve_identity(device_ids)
        meta["simulated"] = bool(ident.get("synthetic"))
        session = await open_or_get_session(conv_id, ident)
    except HTTPException as e:
        await refusal_receipt(device_ids=device_ids, ha_conversation_id=conv_id, utterance=text,
                              reason=str(e.detail))
        raise
    sid = session["session_id"]

    earlier = await claim_turn(session, text)
    if earlier is not None:  # the same utterance again within seconds: an HA retry
        prev = earlier.get("last_response") or {}
        reply = prev.get("response_text") or "One moment, I'm still working on that."
        r = await turn_receipt(session=earlier or session, ident=ident, ha_conversation_id=conv_id,
                               utterance=text, action_type="voice_turn_duplicate_ignored",
                               before=session_state(earlier), after=session_state(earlier),
                               tools=[], results=[], reply=reply, next_state="awaiting_resident")
        return _out(reply, conv_id, sid, bool(prev.get("continue_conversation", True)), [],
                    r["receipt_id"], duplicate=True)

    phrase = ending_phrase(text)
    if phrase:
        name = ident.get("resident_name")
        reply = f"Goodbye{', ' + name if name else ''}. I'm here whenever you need me."
        await _ingest(ident, sid, "user", text)
        await _ingest(ident, sid, "assistant", reply)
        r = await turn_receipt(session=session, ident=ident, ha_conversation_id=conv_id, utterance=text,
                               action_type="voice_session_ended", before=session_state(session),
                               after=session_state(session, status="closed",
                                                   turns=session.get("turn_count", 0) + 1),
                               tools=[], results=[], reply=reply, next_state="idle_wake",
                               extra={"ended_by": "resident_phrase", "phrase": phrase})
        out = _out(reply, conv_id, sid, False, [], r["receipt_id"], session_ended=True)
        await record_turn(sid, r["receipt_id"], out, close=True)
        await _log(sid, ident["room"], "session_ended", {"reason": "resident_phrase", "channel": "voice_bridge"})
        return out

    priority = classify(text)
    if priority == 1:
        return await _emergency_turn(ident, session, conv_id, text)
    # A synthetic (simulator) resident never uses the slots reserved for
    # real staff-help requests.
    admit_prio = 3 if priority == 2 and ident.get("synthetic") else priority
    admitted, waited = await ADMISSION.acquire(admit_prio, MAX_WAIT_S[admit_prio])
    if not admitted:
        return await _deferred_turn(ident, session, conv_id, text, admit_prio, waited)
    try:
        await _ingest(ident, sid, "user", text)
        turn = await _converse(ident, sid, text, budget=min(TURN_BUDGET_SECONDS, 22.0 - waited))
    finally:
        ADMISSION.release()
    meta["error"] = turn["error"]
    reply = turn["reply"]
    await _ingest(ident, sid, "assistant", reply)
    keep_open = not turn["ended"]
    after = session_state(session, status="open" if keep_open else "closed",
                          turns=session.get("turn_count", 0) + 1)
    r = await turn_receipt(
        session=session, ident=ident, ha_conversation_id=conv_id, utterance=text,
        action_type="voice_session_ended" if turn["ended"] else "voice_turn",
        before=session_state(session), after=after, tools=turn["tools"], results=turn["results"],
        reply=reply, next_state="awaiting_resident" if keep_open else "idle_wake",
        status="failed" if turn["error"] else "completed", failure_reason=turn["error"],
        extra={"priority_class": CLASS_NAMES[priority], "queue_wait_ms": round(waited * 1000),
               **({"ended_by": "end_call_tool"} if turn["ended"] else {})})
    out = _out(reply, conv_id, sid, keep_open, turn["tools"], r["receipt_id"],
               priority_class=CLASS_NAMES[priority], queue_wait_ms=round(waited * 1000),
               degraded=bool(turn["error"]))
    await record_turn(sid, r["receipt_id"], out, close=turn["ended"])
    if turn["ended"]:
        await _log(sid, ident["room"], "session_ended", {"reason": "resident_end_call", "channel": "voice_bridge"})
    return out


async def _emergency_turn(ident: dict, session: dict, conv_id: str, text: str) -> dict:
    """Emergency words: escalate through the canonical help path at once -
    no language model, no capacity wait. The reply says only what the
    dispatch confirmed."""
    from routes.ai_escalation import AiEscalateInput, ai_escalate
    sid = session["session_id"]
    await _ingest(ident, sid, "user", text)
    error, result = None, {}
    try:
        result = await ai_escalate(AiEscalateInput(
            reason=f"Resident said: {text[:200]}", severity="emergency", resident_id=ident["resident_id"],
            kiosk_id=ident["kiosk_id"], room=ident["room"], session_id=sid))
    except Exception as e:  # dispatch failure must still be answered and recorded
        error = f"{type(e).__name__}: {str(e)[:200]}"
    state = result.get("wording_state")
    reply = EMERGENCY_REPLY.get(state, EMERGENCY_FAILED)
    await _ingest(ident, sid, "assistant", reply)
    tool = {"name": "call_for_help", "ok": state in EMERGENCY_REPLY}
    res = [("call_for_help", {"alert_id": result.get("alert_id"),
                              "receipt_id": (result.get("dispatch") or {}).get("receipt_id")})] if result else []
    r = await turn_receipt(
        session=session, ident=ident, ha_conversation_id=conv_id, utterance=text,
        action_type="voice_emergency_escalated", before=session_state(session),
        after=session_state(session, turns=session.get("turn_count", 0) + 1), tools=[tool], results=res,
        reply=reply, next_state="staff_responding" if tool["ok"] else "resident_told_to_press_call_button",
        status="completed" if tool["ok"] else "failed",
        failure_reason=error or (None if tool["ok"] else f"dispatch wording_state={state}"),
        extra={"priority_class": "emergency", "queue_wait_ms": 0, "dispatch_state": state})
    out = _out(reply, conv_id, sid, True, [tool], r["receipt_id"], priority_class="emergency")
    await record_turn(sid, r["receipt_id"], out)
    return out


async def _deferred_turn(ident: dict, session: dict, conv_id: str, text: str, priority: int,
                         waited: float) -> dict:
    """No model slot within this class's wait limit: answer now, say so,
    record it. Nothing was executed."""
    sid = session["session_id"]
    await _ingest(ident, sid, "user", text)
    await _ingest(ident, sid, "assistant", DEFERRED_REPLY)
    r = await turn_receipt(
        session=session, ident=ident, ha_conversation_id=conv_id, utterance=text,
        action_type="voice_turn_deferred", before=session_state(session),
        after=session_state(session, turns=session.get("turn_count", 0) + 1), tools=[], results=[],
        reply=DEFERRED_REPLY, next_state="awaiting_resident", status="cancelled",
        failure_reason=f"capacity: no model slot within {MAX_WAIT_S[priority]:.0f}s",
        extra={"priority_class": CLASS_NAMES[priority], "queue_wait_ms": round(waited * 1000),
               "admission": ADMISSION.snapshot()})
    out = _out(DEFERRED_REPLY, conv_id, sid, True, [], r["receipt_id"], deferred=True,
               priority_class=CLASS_NAMES[priority], queue_wait_ms=round(waited * 1000))
    await record_turn(sid, r["receipt_id"], out)
    return out
