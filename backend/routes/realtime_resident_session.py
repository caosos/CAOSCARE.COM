"""Resident session setup: activation fencing and existing voice config.

Split from realtime.py so the resident lifecycle changes do not grow the
already oversized operator/session/SDP module. Provider request/config
behavior is preserved; failures now free only the claim made here.
"""
import httpx
from fastapi import HTTPException
from fastapi.responses import JSONResponse
from routes.realtime import (
    _require_openai_key, DEFAULT_VOICE, ALLOWED_VOICES,
    OPENAI_REALTIME_MODEL, OPENAI_API_BASE, DEFAULT_VAD,
    DEFAULT_NOISE_REDUCTION, DEFAULT_TEMPERATURE, _prompt_diagnostics,
)
from routes.realtime_companion_prompt import _build_companion_instructions
from routes.realtime_facility import get_active_facility, FACILITY_LABEL, FACILITY_TZ
from routes.realtime_tools import _build_tools
from routes.realtime_room_lease import claim_or_reuse_room_lease, release
from routes.resident_session_binding import validate_activation, bind_activation


async def create_resident_session(payload):
    await validate_activation(payload)
    room = payload.get("room")
    lease = None
    if room:
        lease = await claim_or_reuse_room_lease(
            room, payload.get("resident_id"), payload.get("kiosk_id"),
            payload.get("trigger_source") or "manual_kiosk", payload.get("session_id"),
        )
        if not lease["claimed"]:
            return JSONResponse(content={"_caos": {"lease": lease}})
    try:
        await bind_activation(payload, lease["session_id"] if lease else payload.get("session_id"))
        return await _mint(payload, lease)
    except BaseException:
        if lease and lease["claimed"]:
            await release(room, {"session_id": lease["session_id"], "reason": "setup_failed"})
        raise


async def _mint(payload, lease):
    key = _require_openai_key()
    voice = (payload.get("voice") or DEFAULT_VOICE).lower()
    if voice not in ALLOWED_VOICES:
        voice = DEFAULT_VOICE
    facility = await get_active_facility()
    facility_label = (facility or {}).get("name") or FACILITY_LABEL
    facility_tz = (facility or {}).get("timezone") or FACILITY_TZ
    # Level 1 resident-assistance event (2026-09-06): community-configured
    # timeouts, handed to the resident-facing session here rather than via
    # a public config endpoint (the real one is admin-gated).
    from routes.resident_assistance_config import get_effective_config
    assist_cfg = await get_effective_config((facility or {}).get("facility_id"))
    # Conversation substrate Layer E: authoritative "what is actually
    # happening for this resident right now" (open event + open staff
    # requests, real lifecycle + age, current vs background). Aria speaks
    # from this instead of re-reading a stale queue. Best-effort - a
    # lookup failure must never block minting the session.
    from routes.aria_operational_state import resolve_operational_state
    try:
        op_state = await resolve_operational_state(
            payload.get("resident_id"), payload.get("room"), payload.get("alert_id"),
        )
    except Exception:
        op_state = None
    # Conversation substrate Layer B: compact cross-session continuity so a
    # new session is not amnesiac about the one three minutes ago
    # ("I thought I just told you"). Baseline, not workflow - recaps what
    # was said, never marks an old task active. Best-effort.
    from routes.aria_continuity import resolve_continuity
    try:
        continuity = await resolve_continuity(
            payload.get("resident_id"), payload.get("session_id"), payload.get("room"),
        )
    except Exception:
        continuity = None
    # Conversation substrate Layer C: has THIS call (this session_id) already
    # filed or finished a request, or asked a routing question awaiting an
    # answer. Reconnects/`session.update` reuse the same session_id, so this
    # is what stops a mid-call reconnect from re-filing or re-asking. Best-
    # effort - a lookup failure must never block minting the session.
    from routes.aria_conversation_state import resolve_conversation_state
    try:
        conv_state = await resolve_conversation_state(
            payload.get("resident_id"), payload.get("session_id"),
        )
    except Exception:
        conv_state = None
    # Terminal 10 / person-specific interpretation continuity (NON-NEGOTIABLE
    # per AGENTS.md + docs/CAOS_CARE_AGENT_ONBOARDING_CONTRACT.md): bounded,
    # resident-scoped, confirmed heard->understood patterns (e.g. "dos savor"
    # -> "dos sabores" / two flavors). Best-effort.
    from routes.aria_interpretation_patterns import list_patterns
    try:
        interpretation_patterns = await list_patterns(payload.get("resident_id"))
    except Exception:
        interpretation_patterns = None
    instructions = await _build_companion_instructions(
        payload.get("resident_id"), operational_state=op_state, continuity=continuity,
        conversation_state=conv_state, interpretation_patterns=interpretation_patterns,
    )
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
        "tools": await _build_tools(),
        "tool_choice": "auto",
        "turn_detection": DEFAULT_VAD,
        "noise_reduction": DEFAULT_NOISE_REDUCTION,
        "temperature": DEFAULT_TEMPERATURE,
        "lease": lease,
        "context": {
            "resident_id": payload.get("resident_id"),
            "kiosk_id": payload.get("kiosk_id"),
            "room": payload.get("room"),
            "alert_id": payload.get("alert_id"),
            "activation_id": payload.get("activation_id"),
            "facility_label": facility_label,
            "facility_tz": facility_tz,
            "aria_companion_timeout_sec": assist_cfg.get("aria_companion_timeout_sec", 300),
            "invite_silence_sec": assist_cfg.get("invite_silence_sec", 8),
            "live_line_ring_timeout_sec": assist_cfg.get("live_line_ring_timeout_sec", 30),
            "operational_state": op_state,
            "conversation_state": conv_state,
            "interpretation_patterns": interpretation_patterns,
            "continuity": {
                "has_continuity": bool(continuity and continuity.get("has_continuity")),
                "sessions": [{k: v for k, v in s.items() if k != "_rows"}
                             for s in (continuity or {}).get("sessions", [])],
            },
        },
        "diagnostics": _prompt_diagnostics(instructions, "resident_kiosk_realtime"),
    }
    await validate_activation(payload)
    return JSONResponse(content=session)


