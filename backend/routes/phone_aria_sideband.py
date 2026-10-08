"""Sideband control of an accepted handset call: installs tools, persists
transcripts (same db.conversations path as the room session, so request
grounding and memory work unchanged), runs tools, and performs transfers
or hang-ups only after Aria has finished speaking.

The WebSocket is injected (`connect`) so tests drive it with a fake.
"""
import asyncio
import json
import logging
import os
from typing import Awaitable, Callable, Optional

from routes.phone_aria_tools import approved_family_contacts, build_phone_tools, run_phone_tool

log = logging.getLogger("caos.telephony")
TRANSCRIPT_WAIT_SECONDS = 0.9   # same bound as the room path's turn-grounding race


def session_update(tools: list) -> dict:
    from routes.realtime_audio_config import DEFAULT_VAD
    return {"type": "session.update", "session": {
        "type": "realtime",
        "audio": {"input": {"transcription": {"model": "gpt-4o-transcribe"},
                            "noise_reduction": {"type": "near_field"},  # handset at the ear
                            "turn_detection": DEFAULT_VAD}},
        "tools": tools, "tool_choice": "auto"}}


async def _default_connect(openai_call_id: str):
    import websockets  # lazy: only needed when phone Aria is configured
    base = os.environ.get("OPENAI_REALTIME_WS", "wss://api.openai.com/v1/realtime")
    return await websockets.connect(f"{base}?call_id={openai_call_id}",
                                    additional_headers={"Authorization": f"Bearer {os.environ.get('OPENAI_API_KEY', '')}"})


async def _save_turn(call: dict, role: str, text: str) -> None:
    if not call.get("resident_id") or not (text or "").strip():
        return
    from routes.realtime_memory_ingest import RealtimeTurnIngest, store_turn
    try:
        await store_turn(RealtimeTurnIngest(
            resident_id=call["resident_id"], session_id=call["conversation_session_id"],
            role=role, text=text, room=call.get("room")))
    except Exception as e:
        log.warning("phone turn save failed: %s", e)


async def run_sideband(call: dict, *, connect: Optional[Callable] = None,
                       openai_post: Optional[Callable[[str, dict], Awaitable[int]]] = None) -> None:
    from routes.resident_requests import get_request_categories
    if openai_post is None:
        from routes.phone_aria import openai_post as default_post
        openai_post = default_post
    ws = await (connect or _default_connect)(call["openai_call_id"])
    family = await approved_family_contacts(call.get("resident_id"))
    tools = build_phone_tools(family, await get_request_categories())
    state = {"last_user": "", "awaiting_transcript": False, "after_speech": None}
    transcript_ready = asyncio.Event()

    async def send(obj: dict) -> None:
        await ws.send(json.dumps(obj))

    await send(session_update(tools))
    await send({"type": "response.create"})  # greet
    try:
        async for raw in ws:
            msg = json.loads(raw)
            t = msg.get("type")
            if t == "input_audio_buffer.speech_stopped":
                state["awaiting_transcript"] = True
                transcript_ready.clear()
            elif t == "conversation.item.input_audio_transcription.completed":
                state["last_user"] = msg.get("transcript") or ""
                state["awaiting_transcript"] = False
                transcript_ready.set()
                await _save_turn(call, "user", state["last_user"])
            elif t == "response.output_audio_transcript.done":
                await _save_turn(call, "assistant", msg.get("transcript") or "")
            elif t == "response.function_call_arguments.done":
                if state["awaiting_transcript"]:
                    try:
                        await asyncio.wait_for(transcript_ready.wait(), TRANSCRIPT_WAIT_SECONDS)
                    except asyncio.TimeoutError:
                        pass
                try:
                    args = json.loads(msg.get("arguments") or "{}")
                except ValueError:
                    args = {}
                result = await run_phone_tool(msg.get("name", ""), args, call, state["last_user"], openai_post)
                if result.get("after_speech"):
                    state["after_speech"] = result["after_speech"]
                await send({"type": "conversation.item.create", "item": {
                    "type": "function_call_output", "call_id": msg.get("call_id"),
                    "output": json.dumps(result["output"], default=str)}})
                await send({"type": "response.create"})
            elif t == "response.done" and state["after_speech"]:
                action, state["after_speech"] = state["after_speech"], None
                # A tool's own function-output response ends first; act on the
                # response that follows it (Aria's spoken confirmation).
                if msg.get("response", {}).get("output") and not _only_function_calls(msg):
                    await action()
                else:
                    state["after_speech"] = action
    finally:
        try:
            await ws.close()
        except Exception:
            pass


def _only_function_calls(msg: dict) -> bool:
    items = (msg.get("response") or {}).get("output") or []
    return bool(items) and all(i.get("type") == "function_call" for i in items)
