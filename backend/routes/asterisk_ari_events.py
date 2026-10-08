"""Asterisk ARI events -> call state. This is where call-state truth comes
from: Asterisk's own Dial / ChannelDestroyed events, never Aria's words.

Correlation: the dialplan sets the inherited channel variable CAOS_CALL_ID
on every call CAOSCare tracks, and ari.conf lists it in `channelvars`, so it
arrives on each event's channel objects. Events without it are ignored.

The listener connects out to Asterisk's local ARI WebSocket
(/ari/events?app=caoscare&subscribeAll=true) and reconnects with backoff.
It runs only when ASTERISK_ARI_URL is configured.
"""
import asyncio
import json
import logging
import os
from typing import Optional

from routes.call_lifecycle import advance, ensure_call

log = logging.getLogger("caos.telephony")

DIALSTATUS_STATE = {
    "": ("dialing", None),
    "RINGING": ("ringing", None),
    "PROGRESS": ("ringing", "progress"),
    "ANSWER": ("connected", None),
    "NOANSWER": ("unanswered", "no answer"),
    "BUSY": ("unanswered", "busy"),
    "CHANUNAVAIL": ("failed", "endpoint unavailable"),
    "CONGESTION": ("failed", "congestion"),
    "CANCEL": ("ended", "caller hung up before answer"),
}


def _call_id(channel: Optional[dict]) -> Optional[str]:
    return ((channel or {}).get("channelvars") or {}).get("CAOS_CALL_ID") or None


def _caller_ext(channel: Optional[dict]) -> Optional[str]:
    return ((channel or {}).get("caller") or {}).get("number") or None


def interpret(event: dict) -> Optional[tuple]:
    """Pure mapping: ARI event -> (call_id, state, detail, from_extension) or None."""
    etype = event.get("type")
    if etype == "Dial":
        caller, peer = event.get("caller"), event.get("peer")
        call_id = _call_id(caller) or _call_id(peer)
        mapped = DIALSTATUS_STATE.get(event.get("dialstatus") or "")
        if not call_id or not mapped:
            return None
        return (call_id, mapped[0], mapped[1], _caller_ext(caller) or _caller_ext(peer))
    if etype == "ChannelDestroyed":
        channel = event.get("channel")
        call_id = _call_id(channel)
        if not call_id:
            return None
        return (call_id, "ended", event.get("cause_txt") or None, _caller_ext(channel))
    return None


async def handle_event(event: dict) -> Optional[dict]:
    parsed = interpret(event)
    if not parsed:
        return None
    call_id, state, detail, ext = parsed
    call = await ensure_call(call_id, from_extension=ext)
    if not call:
        return None
    result = await advance(call_id, state, source="asterisk", detail=detail)
    if result.get("applied") and call["kind"] == "emergency" and state in ("dialing", "connected"):
        await _record_emergency(call, state)
    return result


async def _record_emergency(call: dict, state: str) -> None:
    """After-the-fact record only. The 911 call itself was already placed by
    the dialplan and the front desk alerted there; nothing here can delay it."""
    if state != "dialing":
        return
    try:
        from routes.notifications import notify_department
        await notify_department(
            "administration", f"CAOSCare: 911 dialed from room {call.get('room') or 'unknown'}",
            f"A 911 call was placed from extension {call.get('from_extension')} "
            f"(room {call.get('room') or 'unknown'}) at {call['created_at']}.",
            related_object_type="call", related_object_id=call["call_id"],
        )
    except Exception as e:  # never let a notification failure surface here
        log.warning("911 notification failed: %s", e)


def ari_ws_url() -> Optional[str]:
    base = os.environ.get("ASTERISK_ARI_URL", "").rstrip("/")
    user = os.environ.get("ASTERISK_ARI_USER", "")
    password = os.environ.get("ASTERISK_ARI_PASSWORD", "")
    if not (base and user and password):
        return None
    ws = base.replace("http://", "ws://").replace("https://", "wss://")
    return f"{ws}/ari/events?app=caoscare&subscribeAll=true&api_key={user}:{password}"


async def run_ari_listener() -> None:
    url = ari_ws_url()
    if not url:
        return
    import websockets  # lazy: only needed when telephony is configured
    delay = 1
    while True:
        try:
            async with websockets.connect(url) as ws:
                log.info("ARI listener connected")
                delay = 1
                async for raw in ws:
                    try:
                        await handle_event(json.loads(raw))
                    except Exception as e:
                        log.warning("ARI event handling failed: %s", e)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            log.warning("ARI listener disconnected (%s); retrying in %ss", e, delay)
        await asyncio.sleep(delay)
        delay = min(delay * 2, 30)
