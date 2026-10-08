"""Endpoints the local Asterisk dialplan calls (func_curl) - never public.

Fail-closed: CAOS_TELEPHONY_TOKEN must be set and sent as
X-CAOS-Telephony-Token, and the caller must be an allowed local host
(CAOS_TELEPHONY_ALLOWED_HOSTS, default loopback). Responses are plain text
because that is what the dialplan's CURL() reads.

Only Aria transfers need CAOSCare before dialing (to resolve the one-time
token to a target). Dial 0, 911 and reaching Aria are pure dialplan, so
they keep working if CAOSCare is down; ARI events record them afterwards.
"""
import os
from datetime import timedelta

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import PlainTextResponse

from deps import db
from models import now_utc

router = APIRouter(prefix="/telephony/local", tags=["telephony-local"])

DIAL_TOKEN_TTL_SECONDS = 120


def _guard(request: Request) -> None:
    token = os.environ.get("CAOS_TELEPHONY_TOKEN", "")
    if not token:
        raise HTTPException(status_code=503, detail="Telephony is not configured on this server")
    allowed = {h.strip() for h in os.environ.get("CAOS_TELEPHONY_ALLOWED_HOSTS", "127.0.0.1,::1").split(",") if h.strip()}
    host = request.client.host if request.client else ""
    if host not in allowed or request.headers.get("x-caos-telephony-token") != token:
        raise HTTPException(status_code=403, detail="Forbidden")


def trunk_endpoint() -> str:
    return os.environ.get("CAOS_SIP_TRUNK_ENDPOINT", "trunk")


@router.get("/dial-target/{token}", response_class=PlainTextResponse)
async def dial_target(token: str, request: Request):
    """Resolve a one-time dial token (from an Aria transfer) to
    "<call_id>|<dial string>". Empty body = refuse; the dialplan then plays
    an apology and records nothing further. Consumes the token."""
    _guard(request)
    cutoff = (now_utc() - timedelta(seconds=DIAL_TOKEN_TTL_SECONDS)).isoformat()
    call = await db.call_sessions.find_one_and_update(
        {"dial_token": token, "state": "requested", "created_at": {"$gte": cutoff}},
        {"$set": {"dial_token": None}}, projection={"_id": 0},
    )
    if not call:
        return ""
    if call["kind"] == "front_desk" and call.get("target_extension"):
        return f"{call['call_id']}|PJSIP/{call['target_extension']}"
    if call["kind"] == "family" and call.get("family_contact_id"):
        contact = await db.family_contacts.find_one(
            {"contact_id": call["family_contact_id"], "resident_id": call.get("resident_id"), "allow_calls": True},
            {"_id": 0, "phone": 1},
        )
        number = normalize_e164((contact or {}).get("phone"))
        if number:
            return f"{call['call_id']}|PJSIP/{number}@{trunk_endpoint()}"
    return ""


def normalize_e164(phone) -> str:
    """Digits-only E.164 for NANP numbers entered by staff; '' if unusable.
    The number always comes from the stored contact, never from speech."""
    digits = "".join(c for c in str(phone or "") if c.isdigit())
    if len(digits) == 10:
        digits = "1" + digits
    if len(digits) == 11 and digits.startswith("1"):
        return "+" + digits
    return ""
