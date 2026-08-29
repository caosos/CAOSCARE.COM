"""Semantic UI-guidance tool schemas for the Admin assistant (2026-08-27,
per Michael's "Aria should visually guide the administrator, not just
describe" directive). Split out of admin_assistant_tools.py (same 300-line
discipline as the rest of this codebase's route-adjacent tool-schema
files).

These tools are READ/NAVIGATION ONLY - they never mutate anything and
must never be described as "configuring" something. Each one resolves its
target against REAL current data (routes.admin_assistant_executor calls
the same domain lookups as the configuration tools) before producing an
ordered ui_action for the frontend to replay - Aria is not allowed to
point at something that doesn't exist.
"""

_SECTIONS = ["residents", "devices", "kiosks", "facilities", "requests", "schedule", "menu", "transportation", "staff", "audit"]


def build_ui_action_tools() -> list[dict]:
    return [
        {
            "type": "function",
            "function": {
                "name": "navigate_admin_section",
                "description": "Bring the administrator's screen to the correct Admin tab/section. Read-only - does not configure anything.",
                "parameters": {
                    "type": "object",
                    "properties": {"section": {"type": "string", "enum": _SECTIONS}},
                    "required": ["section"],
                    "additionalProperties": False,
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "focus_resident",
                "description": (
                    "Navigate to the Residents section AND visibly scroll to/highlight "
                    "one specific resident's row, resolved from real resident data. Use "
                    "this whenever you're about to explain something specific to one "
                    "resident, so the administrator sees exactly who you mean."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {"resident_id": {"type": "string"}, "name": {"type": "string", "description": "If resident_id isn't known yet."}},
                    "additionalProperties": False,
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "focus_room",
                "description": "Navigate to the Devices section and highlight every device registered to one room, resolved from real data.",
                "parameters": {
                    "type": "object",
                    "properties": {"room": {"type": "string"}},
                    "required": ["room"],
                    "additionalProperties": False,
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "focus_device",
                "description": "Navigate to the Devices section and highlight one exact device's row, resolved from real data. Use this right before explaining a specific device's state.",
                "parameters": {
                    "type": "object",
                    "properties": {"device_id": {"type": "string"}},
                    "required": ["device_id"],
                    "additionalProperties": False,
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "highlight_admin_target",
                "description": "Lower-level primitive: just highlight something already visible (or reachable without a full navigate), without changing section. Prefer focus_resident/focus_room/focus_device when applicable - use this only when those don't fit.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "target_type": {"type": "string", "enum": ["resident", "device"]},
                        "target_id": {"type": "string"},
                    },
                    "required": ["target_type", "target_id"],
                    "additionalProperties": False,
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "scroll_to_admin_target",
                "description": "Lower-level primitive: scroll a target into view without highlighting it. Rarely needed on its own - focus_* already scrolls and highlights together.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "target_type": {"type": "string", "enum": ["resident", "device"]},
                        "target_id": {"type": "string"},
                    },
                    "required": ["target_type", "target_id"],
                    "additionalProperties": False,
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "open_item",
                "description": "Open a detail view/dialog for something, if the current screen supports one. Currently a no-op beyond navigating/highlighting if no dedicated detail view is registered for that item type.",
                "parameters": {
                    "type": "object",
                    "properties": {"item_type": {"type": "string"}, "item_id": {"type": "string"}},
                    "required": ["item_type", "item_id"],
                    "additionalProperties": False,
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "close_item",
                "description": "Close a previously opened detail view/dialog.",
                "parameters": {
                    "type": "object",
                    "properties": {"item_type": {"type": "string"}, "item_id": {"type": "string"}},
                    "required": ["item_type", "item_id"],
                    "additionalProperties": False,
                },
            },
        },
    ]
