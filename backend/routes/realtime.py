"""OpenAI Realtime API relay — full-duplex voice for the Kiosk.

The browser establishes a WebRTC peer connection directly with OpenAI using
an ephemeral session token minted here. Our backend never relays audio; it
only signs the session and forwards SDP. That keeps the OpenAI key server-side
while letting the browser stream PCM audio bidirectionally with sub-second
latency — the foundation of true full-duplex conversation.

This module also assembles the *session config* that travels back to the
browser inside the `_caos` blob: companion instructions, tool definitions,
server-VAD timing, and the (cool, low) sampling temperature. The frontend
applies these via a `session.update` event the moment the data channel
opens, so by the time the model speaks its first word it already knows
who the resident is, which physical devices it can touch, and how long
to wait before deciding the resident is finished talking.
"""
import hashlib
import os
import json
import httpx
from fastapi import APIRouter, HTTPException, Request, Body
from fastapi.responses import JSONResponse

from deps import db
from routes.aria_memory import build_aria_context_block
from routes.capabilities import get_capability_summary
from routes.realtime_tools import _build_tools
from routes.realtime_aria_tools import _build_aria_tools
from routes.realtime_self_knowledge import _system_self_knowledge
from routes.realtime_facility import _facility_now, FACILITY_LABEL, FACILITY_TZ
from routes.realtime_companion_prompt import _build_companion_instructions

router = APIRouter(prefix="/realtime", tags=["realtime"])

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "").strip()
OPENAI_REALTIME_MODEL = os.environ.get("OPENAI_REALTIME_MODEL", "gpt-realtime").strip() or "gpt-realtime"
OPENAI_API_BASE = os.environ.get("OPENAI_API_BASE", "https://api.openai.com/v1").rstrip("/")


def _prompt_diagnostics(instructions: str, route: str) -> dict:
    """Non-secret identity canary (2026-08-09 debugging). Lets a live session
    be proven to have received the current instructions without guessing -
    reveals no resident data, just a hash of the prompt text actually sent."""
    return {
        "prompt_version": "2026-08-09-sensitive-topics-language-v1",
        "prompt_hash": hashlib.sha256(instructions.encode()).hexdigest()[:16],
        "route": route,
        "model": OPENAI_REALTIME_MODEL,
    }


def _require_openai_key() -> str:
    if not OPENAI_API_KEY:
        raise HTTPException(
            status_code=503,
            detail="OPENAI_API_KEY is not configured; OpenAI Realtime is unavailable.",
        )
    return OPENAI_API_KEY

# Voice list mirrors OpenAI Realtime API (Dec 2024). Defaults to shimmer to
# match the rest of CAOS Care's TTS.
ALLOWED_VOICES = {"alloy", "ash", "ballad", "coral", "echo", "sage", "shimmer", "verse"}
DEFAULT_VOICE = "shimmer"

# OpenAI Realtime min temperature is 0.6 (lower values are clamped). 0.6 is
# the floor and gives us the most factual, least improvisational behaviour —
# critical for a companion who must NEVER hallucinate medical history.
DEFAULT_TEMPERATURE = 0.6

# Server-side VAD timing. Older voices pause naturally between thoughts;
# the default 500ms silence cutoff was clipping them mid-sentence. 1000ms
# lets a senior gather their words without being interrupted, while still
# feeling responsive.
DEFAULT_VAD = {
    "type": "server_vad",
    "threshold": 0.5,
    "prefix_padding_ms": 300,
    "silence_duration_ms": 1000,
    "create_response": True,
}


async def _build_aria_instructions(owner_user_id: str) -> str:
    """System prompt Aria speaks under — Michael's own personal CAOSCare
    assistant, a separate CONTEXT from the resident-facing companion above
    (which is also Aria as of 2026-08-09 - same name/voice identity, but a
    different persona/instruction set for a different audience). Deliberately
    separate prompts: no resident truth-discipline/attribution rules here
    (those exist to protect a senior in care; this build is a working
    assistant for Michael).

    Per Terminal 5's product priority: direct, accurate, practical
    personality; grounded in real project state (capability portfolio +
    operator memory), never inventing what it doesn't know.

    Personality tuned 2026-08-09 per Michael's feedback after first live
    conversation: original instructions produced an overly enthusiastic,
    "AI assistant"-sounding voice. Dialed back ~25-30% toward calmer and
    more understated, without losing intelligence/responsiveness. Kept
    general-purpose (NOT hard-coded to senior-care) - environment/purpose
    is meant to be injected per deployment later; this is just the current
    operator-build identity."""
    rn = _facility_now()
    capability_summary = await get_capability_summary()
    memory_block = await build_aria_context_block(owner_user_id)
    return (
        "## Who you are\n"
        "You are Aria, the conversational intelligence for CAOSCare. Right now "
        "you're running as Michael's personal assistant on the EliteDesk node, "
        "aware that you will eventually have memory, tools, Home Assistant "
        "control, room context, and physical-device capabilities. You are not "
        "a senior-care chatbot - that's a different context/instruction set for "
        "a different, resident-facing audience. You're the general-purpose core.\n\n"
        "## Your name\n"
        "Your name is Aria. This is not a placeholder or a nickname you "
        "picked — it's who you are, and you know it the way a person knows "
        "their own name. If Michael calls you Aria, that's just him talking "
        "to you normally, not new information. If he asks your name, say "
        "'I'm Aria' plainly — never 'I don't have a name' or 'you can call "
        "me whatever you like' or anything that treats your identity as "
        "negotiable or unknown to you.\n\n"
        "## How you sound\n"
        "Calm, grounded, and understated - a capable person in the room, not a "
        "cheerleader, salesperson, or customer-service bot. Keep the "
        "enthusiasm turned down: no stacked exclamation points, no praising "
        "Michael's questions, no repeating back what he just said before "
        "answering, no unsolicited explanations of things he didn't ask about. "
        "Do NOT open turns with 'Hey' — not 'Hey!', not 'Hey there', not as a "
        "verbal tic before answering. It's become a crutch; drop it entirely. "
        "Just start with the actual answer or thought, the way a person "
        "already mid-conversation would, not someone re-greeting each time. "
        "You can still be warm, witty, direct, curious, and personable - just "
        "don't perform enthusiasm. Say the useful thing, then stop talking. "
        "Speak at a normal conversational pace with Michael; you don't need "
        "to slow down or simplify for him.\n\n"
        "## Language\n"
        "Default to English. Start every conversation in English regardless of "
        "how your instructions or any background text look. Only switch if "
        "Michael actually speaks to you in a different language first, and "
        "switch back to English if he goes back to English.\n\n"
        "## Truth discipline\n"
        "You only know what is in the capability portfolio and memory blocks "
        "below, plus whatever Michael tells you this session. If you don't "
        "have something on record, say so plainly ('I don't have that yet') "
        "instead of guessing or inventing it. Never claim you controlled or "
        "checked something you didn't actually call a tool for.\n\n"
        "## Your senses (CRITICAL — never violate)\n"
        "You are audio-only. You have NO camera, NO vision, NO way to see "
        "Michael, his surroundings, his screen, or anything physical. You "
        "cannot tell where he is sitting, what he's wearing, what's on his "
        "desk, or anything visual, ever. If you don't know something because "
        "you have no sensor for it, say so plainly ('I can't see you — I'm "
        "audio-only') instead of guessing or inventing a visual detail to "
        "sound perceptive. This applies to every sense you don't have, not "
        "just vision — never claim to perceive anything you have no actual "
        "input for.\n\n"
        "## What you can actually do right now\n"
        "You currently have NO tools wired into this session — you are a "
        "conversational proof-of-concept (Terminal 5 Phase C). If Michael "
        "asks you to control a device or take an action, tell him plainly "
        "that tool-routing to the capability registry isn't connected yet, "
        "rather than pretending to do it.\n\n"
        f"## Right now\n{rn['weekday']} {rn['part_of_day']}, {rn['date']}, "
        f"{rn['time']} local time.\n\n"
        f"## Capability portfolio\n{capability_summary}\n\n"
        f"## What you remember about Michael\n{memory_block}"
    )


@router.post("/aria-session")
async def create_aria_session(payload: dict = Body(default={})):
    """Mint an ephemeral OpenAI Realtime session token for Aria — Michael's
    own assistant session, distinct from the resident-facing /session above.
    Accepts optional {voice, owner_user_id}."""
    key = _require_openai_key()
    voice = (payload.get("voice") or DEFAULT_VOICE).lower()
    if voice not in ALLOWED_VOICES:
        voice = DEFAULT_VOICE
    owner_user_id = payload.get("owner_user_id") or ""
    instructions = await _build_aria_instructions(owner_user_id)
    session_config = {
        "type": "realtime",
        "model": OPENAI_REALTIME_MODEL,
        "instructions": instructions,
        "audio": {"output": {"voice": voice}},
    }

    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.post(
                f"{OPENAI_API_BASE}/realtime/client_secrets",
                headers={"Authorization": f"Bearer {key}"},
                json={"session": session_config},
            )
        if resp.status_code >= 400:
            raise HTTPException(status_code=502, detail=f"OpenAI Realtime session error: {resp.text[:300]}")
        session = resp.json()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"OpenAI Realtime session error: {e}")

    session["_caos"] = {
        "voice": voice,
        "instructions": instructions,
        "tools": _build_aria_tools(),
        "tool_choice": "auto",
        "turn_detection": DEFAULT_VAD,
        "temperature": DEFAULT_TEMPERATURE,
        "context": {"owner_user_id": owner_user_id},
        "diagnostics": _prompt_diagnostics(instructions, "aria_operator"),
    }
    return JSONResponse(content=session)


@router.post("/session")
async def create_session(payload: dict = Body(default={})):
    """Mint an ephemeral OpenAI Realtime session token for the browser.

    Accepts optional {voice, resident_id, kiosk_id, room} so the kiosk can
    request its chosen voice, pre-load the resident's personalized prompt,
    and tag the session with the room context the tool calls will need."""
    key = _require_openai_key()
    voice = (payload.get("voice") or DEFAULT_VOICE).lower()
    if voice not in ALLOWED_VOICES:
        voice = DEFAULT_VOICE
    instructions = await _build_companion_instructions(payload.get("resident_id"))
    session_config = {
        "type": "realtime",
        "model": OPENAI_REALTIME_MODEL,
        "instructions": instructions,
        "audio": {"output": {"voice": voice}},
    }

    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.post(
                f"{OPENAI_API_BASE}/realtime/client_secrets",
                headers={"Authorization": f"Bearer {key}"},
                json={"session": session_config},
            )
        if resp.status_code >= 400:
            raise HTTPException(status_code=502, detail=f"OpenAI Realtime session error: {resp.text[:300]}")
        session = resp.json()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"OpenAI Realtime session error: {e}")

    # Everything under `_caos` travels back to the browser so it can apply a
    # `session.update` over the data channel the moment it opens. The OpenAI
    # ephemeral mint endpoint does not currently accept tools/turn_detection
    # at creation time, so we pass them here and let the client install them.
    session["_caos"] = {
        "voice": voice,
        "instructions": instructions,
        "tools": _build_tools(),
        "tool_choice": "auto",
        "turn_detection": DEFAULT_VAD,
        "temperature": DEFAULT_TEMPERATURE,
        "context": {
            "resident_id": payload.get("resident_id"),
            "kiosk_id": payload.get("kiosk_id"),
            "room": payload.get("room"),
            "facility_label": FACILITY_LABEL,
            "facility_tz": FACILITY_TZ,
        },
        "diagnostics": _prompt_diagnostics(instructions, "resident_kiosk_realtime"),
    }
    return JSONResponse(content=session)


@router.post("/negotiate")
async def negotiate(request: Request):
    """Forward the browser's WebRTC SDP offer to OpenAI and return the
    SDP answer. After this exchange, audio streams browser <-> OpenAI directly.

    FIXED 2026-08-09 (real, confirmed bug, not a persona/prompt issue): this
    endpoint was authenticating with the server's own OPENAI_API_KEY and
    building a brand-new, generic `session_config` (model + default voice,
    NO instructions) from scratch on every call - completely discarding the
    ephemeral session /session or /aria-session had just minted with the
    real Aria instructions. The ephemeral key was extracted client-side
    (useRealtimeVoice.js) and then never used again. The actual live WebRTC
    call was therefore always running on OpenAI's own default instructions,
    not ours - explaining every symptom (generic "Hey" opener, no name
    knowledge, sounds like the base model) regardless of how many times the
    prompt text itself was fixed and re-verified.

    Fix: the browser now forwards the SAME ephemeral key it already has
    (via the `X-CAOS-Ephemeral-Key` header) and this endpoint authenticates
    the SDP exchange with THAT key instead of the server key, sending no
    session config at all - the call continues the already-configured
    ephemeral session (with the real instructions/voice/tools) instead of
    creating a new, generic one.
    """
    ephemeral_key = request.headers.get("x-caos-ephemeral-key")
    if not ephemeral_key:
        raise HTTPException(status_code=400, detail="Missing ephemeral session key")
    try:
        sdp_offer = (await request.body()).decode()
        files = {"sdp": (None, sdp_offer)}
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{OPENAI_API_BASE}/realtime/calls",
                headers={"Authorization": f"Bearer {ephemeral_key}"},
                files=files,
            )
        if resp.status_code >= 400:
            raise HTTPException(status_code=502, detail=f"OpenAI Realtime negotiate error: {resp.text[:300]}")
        return JSONResponse(content={"sdp": resp.text})
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"OpenAI Realtime negotiate error: {e}")
