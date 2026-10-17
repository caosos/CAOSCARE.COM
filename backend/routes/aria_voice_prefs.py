"""How Aria talks in each room - kept on the Kiosk record, so any screen showing that kiosk (the room's own page,
or the owner's laptop) changes the room, not one browser. Owner 2026-10-17: low-cost voice by default, a switch to
Realtime "sometimes", the voice picked on the kiosk. Every change is logged (activation log, layer "aria_voice").
"""
import os
from typing import Optional

from fastapi import APIRouter, HTTPException

from deps import db
from routes.aria_voice import TTS_VOICES, enabled

router = APIRouter(prefix="/aria-voice", tags=["realtime"])
TRANSPORTS = {"cascade", "realtime"}


def default_transport() -> str:
    """The room default (ARIA_VOICE_DEFAULT_TRANSPORT); never one that cannot run."""
    t = os.environ.get("ARIA_VOICE_DEFAULT_TRANSPORT", "").strip().lower()
    return "cascade" if enabled() and t == "cascade" else "realtime"


async def _prefs(kiosk_id) -> dict:
    if not kiosk_id:
        return {}
    return await db.kiosks.find_one({"kiosk_id": kiosk_id}, {"_id": 0, "aria_transport": 1, "aria_voice": 1}) or {}


async def session_choice(payload: dict):
    """(transport, voice) for a room session: an explicit request (a test URL), else the kiosk's setting, else the
    room default. The voice is the kiosk's setting, else the page's."""
    prefs = await _prefs(payload.get("kiosk_id"))
    t = payload.get("transport") if payload.get("transport") in TRANSPORTS else prefs.get("aria_transport")
    t = t if t in TRANSPORTS else default_transport()
    if t == "cascade" and not enabled():
        t = "realtime"
    return t, prefs.get("aria_voice") or payload.get("voice")


@router.get("/config")
async def config(kiosk_id: Optional[str] = None):
    """What the room page shows: whether the low-cost voice is available, this kiosk's transport and voice."""
    t, voice = await session_choice({"kiosk_id": kiosk_id})
    return {"cascade_enabled": enabled(), "default_transport": default_transport(), "transport": t, "voice": voice}


@router.post("/kiosks/{kiosk_id}/prefs")
async def set_prefs(kiosk_id: str, payload: dict):
    changes = {}
    if "transport" in payload:
        if payload["transport"] not in TRANSPORTS or (payload["transport"] == "cascade" and not enabled()):
            raise HTTPException(status_code=422, detail="transport must be 'realtime' or an enabled 'cascade'.")
        changes["aria_transport"] = payload["transport"]
    if "voice" in payload:
        v = str(payload["voice"] or "").strip().lower()
        if v not in TTS_VOICES:
            raise HTTPException(status_code=422, detail="Unknown voice.")
        changes["aria_voice"] = v
    if not changes:
        raise HTTPException(status_code=422, detail="Nothing to change.")
    res = await db.kiosks.update_one({"kiosk_id": kiosk_id}, {"$set": changes})
    if not res.matched_count:
        raise HTTPException(status_code=404, detail="Kiosk not found.")
    from routes.activation_log import alog
    await alog("aria_voice", "prefs_changed", kiosk_id=kiosk_id, data=changes)
    return await config(kiosk_id)
