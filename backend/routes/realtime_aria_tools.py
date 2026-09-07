"""Tool schemas for Aria's own operator session (Michael-facing, /aria-session).

Deliberately separate and much smaller than the resident tool catalog in
realtime_tools.py - Aria's own session has had tools:[] since Terminal 5A
by design (prove conversation before tools), but Michael needs at least
the request/status tools tested live, and a way to end gracefully ("that's
all for now") since none exists yet.
"""


from routes.resident_requests import get_request_categories


async def _build_aria_tools() -> list[dict]:
    categories = await get_request_categories()
    return [
        {
            "type": "function",
            "name": "request_staff_help",
            "description": (
                "Create a real, NON-EMERGENCY request routed to a staff "
                "department - pick whichever category in the enum best "
                "matches what's needed. After calling this, tell Michael "
                "the request was CREATED and sent - do not say someone is "
                "already on it or already responded unless "
                "check_request_status confirms that. If the result says "
                "an open request already existed (duplicate/"
                "re_request_count), tell him honestly it was already on "
                "file and you've flagged it again - don't claim a "
                "brand-new request was made."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "category": {
                        "type": "string",
                        "enum": categories,
                        "description": "Which department this should route to."
                    },
                    "summary": {
                        "type": "string",
                        "description": "Short, concrete summary of what's needed - include room/location if Michael mentioned one."
                    },
                    "priority": {
                        "type": "string",
                        "enum": ["low", "normal", "high", "urgent"],
                        "description": "Default 'normal' unless Michael indicates real urgency."
                    }
                },
                "required": ["category", "summary"],
                "additionalProperties": False
            }
        },
        {
            "type": "function",
            "name": "check_request_status",
            "description": (
                "The CURRENT (still-open) status of a request YOU created with "
                "request_staff_help. Use when Michael asks 'did maintenance see "
                "that' or 'any update'. Returns ONLY an open request - if "
                "`found` is false there is nothing pending; say so, don't bring "
                "up a finished one as current. It gives lifecycle times "
                "(`created`, `acknowledged_at`, `started_at`) each with a plain "
                "`label` - use those for 'when' answers; null means unknown, "
                "never guess. `acknowledged_at` means staff have SEEN it; "
                "`in_progress` means work has STARTED - neither means anyone "
                "is on the way. Only claim someone is coming if a real "
                "scheduled window or a dispatch tool result says so. Never "
                "claim acknowledgment/completion it doesn't report."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "category": {
                        "type": "string",
                        "enum": categories,
                        "description": "Optional - narrow to one department's current request."
                    }
                },
                "additionalProperties": False
            }
        },
        {
            "type": "function",
            "name": "end_conversation",
            "description": (
                "Call this when Michael indicates he's done for now - 'that's "
                "all', 'that's all for now', 'we're done', 'goodbye', or "
                "similar. Say a brief, natural sign-off first, then call this "
                "so the session can close cleanly. Do not call this mid-topic "
                "or just because there's a pause."
            ),
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False}
        },
    ]
