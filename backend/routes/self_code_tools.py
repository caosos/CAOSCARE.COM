"""Tool schemas and the one prompt line Room 214 Aria gets for self-inspection.

Declared to the model only when the session being minted is the canonical
Room 214 session (routes.self_code_identity.is_room214_mint). Declaring is
not granting: every call is re-proven server-side by the gate in
routes/self_code_inspection.py. No personality, memory, wake or voice text
lives here - only the minimum capability declaration the owner asked for.
"""
from typing import Optional

from routes.self_code_identity import is_room214_mint

TOOL_NAMES = ("inspect_own_code", "search_own_code", "read_own_code")


def _build_self_code_tools() -> list[dict]:
    return [
        {
            "type": "function",
            "name": "inspect_own_code",
            "description": (
                "Read-only. Reports which CAOSCare source revision you can read, whether "
                "it is the revision actually serving Room 214 right now (backend_match / "
                "frontend_match), and the approved files. Call this first when asked to "
                "look at your own code, check how you work, or whether you can inspect "
                "yourself."
            ),
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
        },
        {
            "type": "function",
            "name": "search_own_code",
            "description": (
                "Read-only literal search over the approved parts of your own source "
                "(realtime session, tools, memory, wake, room page, docs). Use it to find "
                "where something is implemented before reading it. Returns file paths "
                "and line numbers; results are capped."
            ),
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string", "description": "Words or an identifier to find, e.g. 'life_story' or 'toggle_tv'."}},
                "required": ["query"],
                "additionalProperties": False,
            },
        },
        {
            "type": "function",
            "name": "read_own_code",
            "description": (
                "Read-only. Returns a bounded line range (at most 120 lines) of one "
                "approved repo-relative source file, e.g. 'backend/routes/aria_life_memory.py'. "
                "Only files inspect_own_code lists are readable; nothing can be written."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Repo-relative path from the approved list."},
                    "start_line": {"type": "integer", "minimum": 1, "description": "First line (1-based). Default 1."},
                    "end_line": {"type": "integer", "minimum": 1, "description": "Last line (inclusive), at most start_line + 119."},
                },
                "required": ["path"],
                "additionalProperties": False,
            },
        },
    ]


def self_code_prompt_block() -> str:
    return (
        "\n## Your own source code (this verified Room 214 session only)\n"
        "You have three read-only tools over the approved parts of your own CAOSCare "
        "implementation: inspect_own_code (which revision you are reading, whether it is "
        "the one serving this room, and the approved files), search_own_code (find where "
        "something is implemented), read_own_code (read a bounded range of one approved "
        "file). When asked how you work or why you did something, use them and answer from "
        "what you actually read, in plain spoken language, naming the files you looked at. "
        "Every result says whether the inspected revision matches the code serving Room 214: "
        "say 'I checked the code I'm currently running' only when it reports a match; "
        "otherwise say you found it in the repository but it is not the version running "
        "here. You cannot change, write, run, restart or deploy anything - you have no tool "
        "or authority for that; if asked, say so plainly.\n"
    )


async def self_code_session_extras(payload: dict, lease: Optional[dict]) -> dict:
    """{"tools": [...], "prompt": "..."} for the canonical Room 214 mint, else
    empty - so no other session ever sees the capability declared."""
    if not await is_room214_mint(payload, lease):
        return {"tools": [], "prompt": "", "enabled": False}
    return {"tools": _build_self_code_tools(), "prompt": self_code_prompt_block(), "enabled": True}
