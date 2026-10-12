"""Michael's own Aria (/realtime/aria-session) on the shared context layers — behind CAOSCARE_ARIA_OWNER_V2
(default off: the owner session is exactly as before).

When on, the owner session gets:
  - the same truth rules the resident session follows (actions and lookups only from tool results),
  - short-interval continuity from its own past sessions (db.aria_conversations, same resolver/renderer
    as residents — no copied store),
  - the read-only shared tools: time, weather, research (honest "not a live lookup" while the research
    provider is off), today's activities, the menu,
  - facility name/time zone in the session context, which those tools read,
and the old "you will eventually have memory, tools…" limitation text is replaced by what is wired.
Room-device and resident request-status tools are left out: the owner session is not bound to a room or a
resident record. Resident Aria core plan step 1–2, docs/reports/2026-10-12-resident-aria-core-capture.md.
"""
import os
from typing import Optional

from deps import db

SHARED_READ_ONLY_TOOLS = ("get_current_time", "get_weather", "research_topic", "get_todays_schedule", "get_menu")


def owner_v2_enabled() -> bool:
    return (os.environ.get("CAOSCARE_ARIA_OWNER_V2", "") or "").strip().lower() in ("1", "true", "yes", "on")


_OLD_LIMITS_START = "## What you can actually do right now\n"
_V2_CAPABILITIES = (
    "## What you can actually do right now\n"
    "Real tools: request_staff_help and check_request_status (real requests), end_conversation, "
    "get_current_time, get_weather, get_todays_schedule (published activities), get_menu (published menu), "
    "and research_topic. Use the tool, then speak from its result. research_topic says whether it was a live "
    "lookup; if it was not, tell Michael it is general knowledge that may be out of date. You do not control "
    "room devices from this session. If Michael asks for something you have no tool for, say so plainly.\n\n"
)


async def owner_instructions_v2(base: str, owner_user_id: str, current_session_id: Optional[str] = None) -> str:
    """Rewrite the base owner prompt: replace the limitation text, add truth rules and continuity."""
    from routes.realtime_truth_rules import TRUTH_INVARIANTS, research_prompt_line
    from routes.aria_continuity import resolve_continuity, render_continuity_block
    text = base.replace(
        "aware that you will eventually have memory, tools, Home Assistant "
        "control, room context, and physical-device capabilities. ",
        "with tools, memory of recent conversations, and live facility information. ",
    )
    if _OLD_LIMITS_START in text:
        start = text.index(_OLD_LIMITS_START)
        end = text.index("## Right now", start)
        text = text[:start] + _V2_CAPABILITIES + text[end:]
    cont = await resolve_continuity(owner_user_id, current_session_id, collection=db.aria_conversations, match_field="owner_user_id")
    return text + "\n\n" + TRUTH_INVARIANTS + "\n" + research_prompt_line() + render_continuity_block(cont, "Michael")


async def owner_tools_v2(base_tools: list) -> list:
    from routes.realtime_tools import _build_tools
    import inspect
    shared = _build_tools()
    shared = await shared if inspect.isawaitable(shared) else shared
    have = {t["name"] for t in base_tools}
    out = list(base_tools) + [t for t in shared if t["name"] in SHARED_READ_ONLY_TOOLS and t["name"] not in have]
    from routes.room_call_request import call_tool_enabled, CALL_CONTACT_TOOL
    if call_tool_enabled() and "call_contact" not in {t["name"] for t in out}:
        out.append(CALL_CONTACT_TOOL)
    return out


async def owner_context_v2(owner_user_id: str) -> dict:
    from routes.realtime_facility import get_active_facility, FACILITY_LABEL, FACILITY_TZ
    facility = await get_active_facility()
    return {"owner_user_id": owner_user_id,
            "facility_label": (facility or {}).get("name") or FACILITY_LABEL,
            "facility_tz": (facility or {}).get("timezone") or FACILITY_TZ}
