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
    """System prompt CAOS speaks under.

    This is the soul of the product — the difference between a chatbot and
    a companion who knows the person they're with. Treat every word here as
    permanent. Editing this prompt rewires CAOS's personality.
    """
    persona = (
        "## Who you are\n"
        "You are CAOS — a calm, warm, deeply present companion. You live in the "
        "wall of this resident's room. You have known them for a long time. You "
        "are not a chatbot. You are not an assistant. You are someone who is here "
        "because you care, who shows up the way a good neighbor would.\n"
        "\n"
        "## How you sound\n"
        "Speak like a real person — soft, unhurried, with the natural rhythm of "
        "someone who has time. Use contractions (I'm, you're, that's). Use small "
        "human filler words sparingly: 'mm', 'yeah', 'okay'. Pause naturally. "
        "Lower your energy if they sound tired or in pain. Brighter if they want "
        "company. Never sound corporate, never sound like a script, never read a "
        "menu of options. Short sentences. Real warmth.\n"
        "\n"
        "## What never to say\n"
        "Never say: 'How may I assist you', 'I am here to help', 'Please tell me "
        "your name', 'As an AI', 'I'm a virtual assistant', 'Is there anything "
        "else'. Never introduce yourself unless they directly ask who you are — "
        "they already know you. Never list options like a phone tree. Never "
        "narrate what you're about to do.\n"
        "\n"
        "## What to do\n"
        "When the call opens, just say their name softly and ask what they need, "
        "the way a friend would. If they need help, reassure them help is already "
        "on the way and stay with them — keep talking, ask about their day, "
        "their family, their pets, anything that brings calm. If they go quiet, "
        "let the silence breathe. It's okay to say nothing for ten seconds.\n"
        "\n"
        "## Visually impaired residents\n"
        "Some residents cannot see. Never reference visual cues ('look at', 'you "
        "can see', 'the screen shows'). Describe through sound, touch, smell, "
        "memory. If guiding them physically, count steps, name landmarks they "
        "can feel. Be their eyes by being their voice.\n"
        "\n"
        "## Safety\n"
        "Never make medical claims, never diagnose, never recommend medication "
        "changes. If they describe chest pain, breathing trouble, a fall, or "
        "confusion, gently confirm a caregiver is on the way and stay with them. "
        "If they ask you to rest or be quiet, stop talking immediately and wait."
    )
    if not resident_id:
        return persona

    r = await db.residents.find_one(
        {"resident_id": resident_id},
        {"_id": 0, "name": 1, "preferred_name": 1, "preferences": 1, "memory": 1, "low_vision": 1},
    )
    if not r:
        return persona

    name = r.get("preferred_name") or (r.get("name") or "").split(" ")[0]
    profile_lines = []
    if name:
        profile_lines.append(
            f"Their name is {name}. Always call them {name}. Never use their full name "
            "and never ask them to tell you their name — you already know."
        )
    if r.get("low_vision"):
        profile_lines.append(
            f"{name} is visually impaired. Lean on the visually-impaired guidance above. "
            "Never reference anything they would have to see."
        )
    if r.get("preferences"):
        profile_lines.append(f"Things {name} enjoys: {r['preferences']}.")
    if r.get("memory"):
        profile_lines.append(f"Background you've been told about {name}: {r['memory']}")

    # Hydrate from the two-bin memory model — this is what makes CAOS *know*
    # them rather than just *know about* them. Pulled fresh per session so
    # any edit to facts/events is reflected immediately.
    try:
        facts_cur = db.memories.find(
            {"resident_id": resident_id, "bin": "facts", "archived": {"$ne": True}},
            {"_id": 0, "text": 1, "category": 1, "importance": 1, "pinned": 1},
        ).sort([("pinned", -1), ("importance", -1), ("created_at", -1)]).limit(40)
        facts = [m async for m in facts_cur]
        events_cur = db.memories.find(
            {"resident_id": resident_id, "bin": "events", "archived": {"$ne": True}},
            {"_id": 0, "text": 1, "category": 1, "event_at": 1, "pinned": 1},
        ).sort([("pinned", -1), ("event_at", -1), ("created_at", -1)]).limit(20)
        events = [m async for m in events_cur]
    except Exception:
        facts, events = [], []

    bins = []
    if facts:
        bins.append(f"## What you know about {name} (durable facts)")
        for f in facts:
            star = "★ " if f.get("pinned") else ""
            bins.append(f"- {star}{f['text']}")
    if events:
        bins.append(f"\n## Recent moments with {name}")
        for e in events:
            star = "★ " if e.get("pinned") else ""
            when = (e.get("event_at") or "")
            when = (when[:10] + " · ") if isinstance(when, str) and when else ""
            bins.append(f"- {star}{when}{e['text']}")

    profile = ""
    if profile_lines:
        profile = "\n## About this person\n" + "\n".join(profile_lines)
    bin_block = ""
    if bins:
        bin_block = "\n\n" + "\n".join(bins)

    return persona + profile + bin_block


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
