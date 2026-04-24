"""OpenAI Realtime API relay — full-duplex voice for the Kiosk.

The browser establishes a WebRTC peer connection directly with OpenAI using
an ephemeral session token minted here. Our backend never relays audio; it
only signs the session and forwards SDP. That keeps the OpenAI key server-side
while letting the browser stream PCM audio bidirectionally with sub-second
latency — the foundation of true full-duplex conversation.
"""
import os
from fastapi import APIRouter, HTTPException, Request, Body
from fastapi.responses import JSONResponse
from emergentintegrations.llm.openai import OpenAIChatRealtime

from deps import db

router = APIRouter(prefix="/realtime", tags=["realtime"])

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
_realtime = OpenAIChatRealtime(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None

# Voice list mirrors OpenAI Realtime API (Dec 2024). Defaults to shimmer to
# match the rest of CAOS Care's TTS.
ALLOWED_VOICES = {"alloy", "ash", "ballad", "coral", "echo", "sage", "shimmer", "verse"}
DEFAULT_VOICE = "shimmer"


async def _build_companion_instructions(resident_id: str | None) -> str:
    """System prompt CAOS speaks under. Mirrors the personality used in
    /api/ai/chat so the realtime voice loop is the same companion residents
    already trust."""
    base = (
        "You are CAOS, a calm and warm companion in a senior-living facility. "
        "Speak gently, briefly, and let the resident lead. If they ask for help, "
        "reassure them help is on the way. Never make medical claims. Be patient "
        "with silence — it's okay to wait. If they tell you to rest or be quiet, "
        "stop talking immediately. Use short sentences. Match their tone — "
        "lower energy if they sound tired, brighter if they want company."
    )
    if not resident_id:
        return base
    r = await db.residents.find_one(
        {"resident_id": resident_id},
        {"_id": 0, "name": 1, "preferred_name": 1, "preferences": 1, "memory": 1},
    )
    if not r:
        return base
    name = r.get("preferred_name") or (r.get("name") or "").split(" ")[0]
    extras = []
    if name:
        extras.append(f"You are speaking with {name}.")
    if r.get("preferences"):
        extras.append(f"They enjoy: {r['preferences']}.")
    if r.get("memory"):
        extras.append(f"Background: {r['memory']}")
    return base + " " + " ".join(extras)


@router.post("/session")
async def create_session(payload: dict = Body(default={})):
    """Mint an ephemeral OpenAI Realtime session token for the browser.
    Accepts optional {voice, resident_id} so the kiosk can request its
    chosen voice and pre-load the resident's personalized prompt."""
    if not _realtime:
        raise HTTPException(status_code=503, detail="OPENAI_API_KEY not configured")
    voice = (payload.get("voice") or DEFAULT_VOICE).lower()
    if voice not in ALLOWED_VOICES:
        voice = DEFAULT_VOICE
    try:
        session = await _realtime.create_ephemeral_session_for_audio_chat(voice=voice)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"OpenAI session error: {e}")
    # Attach our companion instructions so the frontend can session.update them
    instructions = await _build_companion_instructions(payload.get("resident_id"))
    session["_caos"] = {"voice": voice, "instructions": instructions}
    return JSONResponse(content=session)


@router.post("/negotiate")
async def negotiate(request: Request):
    """Forward the browser's WebRTC SDP offer to OpenAI and return the
    SDP answer. After this exchange, audio streams browser ↔ OpenAI directly."""
    if not _realtime:
        raise HTTPException(status_code=503, detail="OPENAI_API_KEY not configured")
    try:
        sdp_offer = (await request.body()).decode()
        sdp_answer = await _realtime.negotiate_connection(sdp_offer)
        return JSONResponse(content={"sdp": sdp_answer})
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Negotiate error: {e}")
