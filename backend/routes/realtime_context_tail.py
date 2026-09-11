"""Assembles the Aria-owned context tail appended after the fixed persona
in the resident companion prompt - one place for the concatenation order so
_build_companion_instructions (realtime_companion_prompt.py) doesn't keep
growing a render_* import + append line per substrate layer.

Order (durable -> recent -> this call -> right now):
  interpretation patterns (durable, person-specific - Terminal 10)
  -> continuity (Layer B: cross-session recap)
  -> conversation state (Layer C: this call's own state, may defer to E)
  -> operational state (Layer E: authoritative right now, kept last/freshest)
"""
from typing import Optional

from routes.realtime_operational_context import render_operational_block
from routes.aria_continuity import render_continuity_block
from routes.aria_conversation_state import render_conversation_state_block
from routes.aria_interpretation_patterns import render_interpretation_block


def render_context_tail(
    name: str,
    operational_state: Optional[dict] = None,
    continuity: Optional[dict] = None,
    conversation_state: Optional[dict] = None,
    interpretation_patterns: Optional[list] = None,
) -> str:
    return (
        render_interpretation_block(interpretation_patterns, name)
        + render_continuity_block(continuity, name)
        + render_conversation_state_block(conversation_state, operational_state)
        + render_operational_block(operational_state)
    )
