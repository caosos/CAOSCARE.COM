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
import json
import os
import re
import time
import uuid
from typing import Optional

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from deps import db
from routes.ai import OPENAI_TEXT_MODEL, _post_openai
from routes.arrival_claim_guard import candidate_tasks, guard_reply
from routes.realtime_diagnostics import DiagnosticEvent, log_event
from routes.realtime_memory_ingest import RealtimeTurnIngest, realtime_turn_ingest
from routes.resident_conversation_context import build_resident_instructions
from routes.voice_bridge_receipts import refusal_receipt, turn_receipt
from routes.voice_bridge_session import (claim_turn, ending_phrase, open_or_get_session,
                                         record_turn, resolve_identity, session_state)
from routes.voice_bridge_tools import ENDING_TOOLS, bridge_tool_schemas, run_bridge_tool

router = APIRouter(prefix="/voice-bridge", tags=["voice-bridge"])

MAX_TOOL_ROUNDS = 4
HISTORY_TURNS = 20
TURN_BUDGET_SECONDS = float(os.environ.get("CAOSCARE_VOICE_BRIDGE_BUDGET_S", "18"))
MODEL = os.environ.get("CAOSCARE_VOICE_BRIDGE_MODEL") or OPENAI_TEXT_MODEL
CHANNEL_NOTE = (
    "\n\n## This conversation's channel\n"
    "You are speaking through the room's voice satellite: the resident's words "
    "reach you as text from speech recognition and your reply is read aloud. "
    "Reply in one to three short spoken sentences, no lists, no markup.\n"
)
FAILURE_REPLY = ("I'm having trouble right now. If you need help, please press your "
                 "call button or ask again in a moment.")
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


async def _converse(ident: dict, session_id: str, text: str) -> dict:
    """The model/tool loop. Tools run to completion once started (never
    cancelled mid-write); the time budget only stops further model calls."""
    ctx_payload = {"resident_id": ident["resident_id"], "room": ident["room"], "session_id": session_id}
    built = await build_resident_instructions(ctx_payload)
    messages = [{"role": "system", "content": built["instructions"] + CHANNEL_NOTE}]
    messages += await _history(session_id)
    tools = await bridge_tool_schemas()
    tool_ctx = {**ctx_payload, "last_user_text": text,
                "origin_authority": f"registered_endpoint:{ident['kiosk_id']}"}
    used, results, ended, reply, error = [], [], False, "", None
    deadline = time.monotonic() + TURN_BUDGET_SECONDS
    for _ in range(MAX_TOOL_ROUNDS + 1):
        remaining = deadline - time.monotonic()
        if remaining < 1:
            error = "turn time budget exhausted"
            break
        try:
            resp = await asyncio.to_thread(_post_openai, "/chat/completions", {
                "model": MODEL, "messages": messages, "tools": tools, "tool_choice": "auto"},
                timeout=max(1, int(remaining)))
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
    return {"response_text": reply, "conversation_id": conv_id, "session_id": session_id,
            "continue_conversation": keep_open, "tools_used": [t["name"] for t in tools],
            "receipt_id": receipt_id, **extra}


@router.post("/turn")
async def voice_bridge_turn(data: VoiceBridgeTurn, authorization: Optional[str] = Header(None)):
    _check_token(authorization)
    text = (data.text or "").strip()
    if not text:
        raise HTTPException(422, "empty transcript")
    conv_id = data.conversation_id or uuid.uuid4().hex[:16]
    device_ids = [data.device_id, data.satellite_id]
    try:
        ident = await resolve_identity(device_ids)
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

    await _ingest(ident, sid, "user", text)
    turn = await _converse(ident, sid, text)
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
        extra={"ended_by": "end_call_tool"} if turn["ended"] else None)
    out = _out(reply, conv_id, sid, keep_open, turn["tools"], r["receipt_id"])
    await record_turn(sid, r["receipt_id"], out, close=turn["ended"])
    if turn["ended"]:
        await _log(sid, ident["room"], "session_ended", {"reason": "resident_end_call", "channel": "voice_bridge"})
    return out
