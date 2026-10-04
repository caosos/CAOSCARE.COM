"""Resident conversation context — the one place a resident session's
instructions are assembled (substrate layers B/C/E, interpretation
patterns, persona/name). Used by the realtime mint and the voice bridge so
both speak from the same context.
"""
from routes.realtime_companion_prompt import _build_companion_instructions


async def build_resident_instructions(payload: dict, tools: tuple | None = None,
                                     channel: str = "kiosk") -> dict:
    """`tools`: the tool names this conversation actually provides (None =
    the realtime room session's set). `channel`: "kiosk" or "voice"."""
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
        tools=tools, channel=channel,
    )
    return {"instructions": instructions, "op_state": op_state, "continuity": continuity,
            "conv_state": conv_state, "interpretation_patterns": interpretation_patterns}
