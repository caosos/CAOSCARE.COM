"""Aria on the room handset, via OpenAI Realtime SIP.

Asterisk sends the Aria extension to OpenAI's SIP endpoint with the headers
X-CAOS-Call-Id (the dialplan's CAOS_CALL_ID) and X-CAOS-Extension (the
handset's extension). OpenAI posts
`realtime.call.incoming` here; we accept the call with the resident's
instructions and run tools over the sideband WebSocket
(routes/phone_aria_sideband.py). Verified against the current OpenAI SIP
guide 2026-09-27 (accept/refer/hangup endpoints, Standard Webhooks signing).

This URL must be reachable by OpenAI (see docs/PILOT1_COMMUNICATIONS.md -
a tunnel to the EliteDesk). Dial 0 and 911 never depend on it.
"""
import asyncio
import json
import logging
import os
from typing import Optional

import httpx
from fastapi import APIRouter, HTTPException, Request

from deps import db
from routes.call_lifecycle import advance, ensure_call
from routes.email_inbound_signature import verify_standard_webhook, WebhookVerificationError
from routes.phone_aria_tools import approved_family_contacts

log = logging.getLogger("caos.telephony")
router = APIRouter(prefix="/telephony/openai", tags=["telephony"])
_tasks: set = set()


def _openai_base() -> str:
    return os.environ.get("OPENAI_API_BASE", "https://api.openai.com/v1").rstrip("/")


async def openai_post(path: str, body: dict) -> int:
    key = os.environ.get("OPENAI_API_KEY", "")
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.post(f"{_openai_base()}{path}", json=body, headers={"Authorization": f"Bearer {key}"})
    if r.status_code >= 300:
        log.warning("OpenAI %s -> %s %s", path, r.status_code, r.text[:200])
    return r.status_code


def _header(sip_headers: list, name: str) -> Optional[str]:
    for h in sip_headers or []:
        if (h.get("name") or "").lower() == name.lower():
            return h.get("value")
    return None


async def build_phone_instructions(call: dict) -> str:
    from routes.realtime_companion_prompt import _build_companion_instructions
    resident_id = call.get("resident_id")
    op_state = continuity = None
    try:
        from routes.aria_operational_state import resolve_operational_state
        op_state = await resolve_operational_state(resident_id, call.get("room"), None)
    except Exception:
        pass
    try:
        from routes.aria_continuity import resolve_continuity
        continuity = await resolve_continuity(resident_id, call.get("conversation_session_id"), call.get("room"))
    except Exception:
        pass
    base = await _build_companion_instructions(resident_id, operational_state=op_state, continuity=continuity)
    family = await approved_family_contacts(resident_id)
    who = ", ".join(f"{c['name']} ({c.get('relationship') or 'family'})" for c in family) \
        or "nobody yet - offer to ask the front desk to set that up"
    return base + (
        "\n\n## On the telephone\n"
        "You are speaking with the resident on the telephone handset in their room, not the room speaker. "
        "On this call you can file a staff request, check an open request, connect them to the front desk, "
        f"call an approved family member ({who}), and hang up when they say goodbye. You cannot control lights, "
        "the TV or the thermostat on this call.\n"
        "If they describe an emergency or ask for 911: tell them clearly to hang up and dial 9 1 1 on this "
        "phone, or press their pendant. You cannot place emergency calls.\n"
        "When you connect a call, say who you are connecting them to. Never say anyone answered."
    )


def phone_voice() -> str:
    from routes.realtime import DEFAULT_VOICE
    return os.environ.get("CAOS_PHONE_VOICE", DEFAULT_VOICE)


@router.post("/webhook")
async def openai_call_webhook(request: Request):
    secret = os.environ.get("OPENAI_WEBHOOK_SECRET", "")
    if not secret:
        raise HTTPException(status_code=503, detail="Phone Aria is not configured on this server")
    raw = await request.body()
    try:
        verify_standard_webhook(secret=secret, msg_id=request.headers.get("webhook-id"),
                                timestamp=request.headers.get("webhook-timestamp"),
                                signature=request.headers.get("webhook-signature"), body=raw)
    except WebhookVerificationError as e:
        raise HTTPException(status_code=401, detail=f"Webhook verification failed: {e}")
    payload = json.loads(raw)
    if payload.get("type") != "realtime.call.incoming":
        return {"ok": True, "ignored": payload.get("type")}
    data = payload.get("data") or {}
    openai_call_id = data.get("call_id")
    caos_id = _header(data.get("sip_headers"), "X-CAOS-Call-Id") or ""
    ext = _header(data.get("sip_headers"), "X-CAOS-Extension")
    call = await ensure_call(caos_id, from_extension=ext) if caos_id.startswith("aria-") else None
    if not openai_call_id or not call:
        if openai_call_id:
            await openai_post(f"/realtime/calls/{openai_call_id}/reject", {})
        return {"ok": True, "rejected": "unknown call"}
    if call.get("openai_call_id") == openai_call_id:
        return {"ok": True, "duplicate": True}  # webhook retry
    await db.call_sessions.update_one({"call_id": call["call_id"]}, {"$set": {"openai_call_id": openai_call_id}})
    call["openai_call_id"] = openai_call_id
    from routes.realtime import OPENAI_REALTIME_MODEL
    status = await openai_post(f"/realtime/calls/{openai_call_id}/accept", {
        "type": "realtime", "model": OPENAI_REALTIME_MODEL,
        "instructions": await build_phone_instructions(call),
        "audio": {"output": {"voice": phone_voice()}},
    })
    if status >= 300:
        await advance(call["call_id"], "failed", source="openai", detail=f"accept rejected ({status})")
        return {"ok": True, "accepted": False}
    from routes.phone_aria_sideband import run_sideband
    task = asyncio.create_task(run_sideband(call))
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)
    return {"ok": True, "accepted": True, "call_id": call["call_id"]}
