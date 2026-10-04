"""Voice bridge (spike): one resident conversation turn as text.

For a Home Assistant custom conversation agent (Voice PE → HA wake word +
speech-to-text → this endpoint → reply text → HA text-to-speech). This is
HA's staged path, not the browser's realtime speech-to-speech session.

CAOSCare stays the owner of the conversation: the room comes from a
registered endpoint (an existing Kiosk record), turns go to the same
conversation store as realtime calls, the instructions are the same
resident instructions the realtime mint builds, and every action runs
through the canonical services (voice_bridge_tools.py). HA holds no
resident or workflow data.

Auth: a shared bridge credential (CAOSCARE_VOICE_BRIDGE_TOKEN) proves the
caller is the configured HA integration; the speaker is still an
unverified room claim, exactly as for the room screen and Aria voice.
"""
import asyncio
import hmac
import json
import os
import re
import uuid
from typing import Optional

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from deps import db
from routes.ai import OPENAI_TEXT_MODEL, _post_openai
from routes.arrival_claim_guard import candidate_tasks, guard_reply
from routes.realtime_diagnostics import DiagnosticEvent, log_event
from routes.realtime_memory_ingest import RealtimeTurnIngest, realtime_turn_ingest
from routes.resident_conversation_context import build_resident_instructions
from routes.voice_bridge_tools import ENDING_TOOLS, bridge_tool_schemas, run_bridge_tool

router = APIRouter(prefix="/voice-bridge", tags=["voice-bridge"])

MAX_TOOL_ROUNDS = 4
HISTORY_TURNS = 20
CHANNEL_NOTE = (
    "\n\n## This conversation's channel\n"
    "You are speaking through the room's voice satellite: the resident's words "
    "reach you as text from speech recognition and your reply is read aloud. "
    "Reply in one to three short spoken sentences, no lists, no markup.\n"
)


class VoiceBridgeTurn(BaseModel):
    endpoint_id: str = Field(..., description="registered room endpoint (kiosk_id)")
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


@router.post("/turn")
async def voice_bridge_turn(data: VoiceBridgeTurn, authorization: Optional[str] = Header(None)):
    _check_token(authorization)
    text = (data.text or "").strip()
    if not text:
        raise HTTPException(422, "empty transcript")
    kiosk = await db.kiosks.find_one({"kiosk_id": data.endpoint_id}, {"_id": 0})
    if not kiosk or not kiosk.get("room"):
        raise HTTPException(404, "unknown room endpoint")
    room = kiosk["room"]
    resident = await db.residents.find_one({"room": room}, {"_id": 0, "resident_id": 1})
    if not resident:
        raise HTTPException(404, "no resident is assigned to this room endpoint")
    resident_id = resident["resident_id"]
    session_id = _session_id(data.conversation_id)

    await realtime_turn_ingest(RealtimeTurnIngest(
        resident_id=resident_id, session_id=session_id, role="user", text=text,
        room=room, kiosk_id=data.endpoint_id))
    ctx_payload = {"resident_id": resident_id, "room": room, "session_id": session_id}
    built = await build_resident_instructions(ctx_payload)
    messages = [{"role": "system", "content": built["instructions"] + CHANNEL_NOTE}]
    messages += await _history(session_id)
    tools = await bridge_tool_schemas()
    tool_ctx = {**ctx_payload, "last_user_text": text,
                "origin_authority": f"registered_endpoint:{data.endpoint_id}"}
    used, results, ended, reply = [], [], False, ""

    for _ in range(MAX_TOOL_ROUNDS + 1):
        resp = await asyncio.to_thread(_post_openai, "/chat/completions", {
            "model": OPENAI_TEXT_MODEL, "messages": messages,
            "tools": tools, "tool_choice": "auto"})
        msg = resp["choices"][0]["message"]
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
            await _log(session_id, room, "tool_call", {"name": name, "args": args, "channel": "voice_bridge"})
            result = await run_bridge_tool(name, args, tool_ctx)
            await _log(session_id, room, "tool_result", {"name": name, "result": result})
            used.append(name)
            results.append(result)
            ended = ended or (name in ENDING_TOOLS and result.get("ok"))
            messages.append({"role": "tool", "tool_call_id": call["id"],
                             "content": json.dumps(result, default=str)})
    if not reply:
        reply = "I'm sorry, I couldn't finish that just now."
    reply, removed = await guard_reply(reply, await candidate_tasks(results, resident_id))
    if removed:
        await _log(session_id, room, "reply_guarded", {"removed": removed, "reason": "arrival_claim_without_claim_receipt"})

    await realtime_turn_ingest(RealtimeTurnIngest(
        resident_id=resident_id, session_id=session_id, role="assistant", text=reply,
        room=room, kiosk_id=data.endpoint_id))
    if ended:
        await _log(session_id, room, "session_ended", {"reason": "resident_end_call", "channel": "voice_bridge"})
    return {"response_text": reply, "conversation_id": data.conversation_id or session_id[3:],
            "session_id": session_id, "continue_conversation": not ended, "tools_used": used}
