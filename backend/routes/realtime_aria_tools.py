"""Tool schemas for Aria's own operator session (Michael-facing, /aria-session).

Deliberately separate and much smaller than the resident tool catalog in
realtime_tools.py - Aria's own session has had tools:[] since Terminal 5A
by design (prove conversation before tools), but Michael needs at least
the request/status tools tested live, and a way to end gracefully ("that's
all for now") since none exists yet.
"""


def _build_aria_tools() -> list[dict]:
    return [
        {
            "type": "function",
            "name": "request_staff_help",
            "description": (
                "Create a real, NON-EMERGENCY request routed to a staff "
                "department - nursing, maintenance (something broken), "
                "kitchen, front_desk, housekeeping, or complaint. After "
                "calling this, tell Michael the request was CREATED and "
                "sent - do not say someone is already on it or already "
                "responded unless check_request_status confirms that."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "category": {
                        "type": "string",
                        "enum": ["nursing", "maintenance", "kitchen", "front_desk", "housekeeping", "complaint"],
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
                "Check the real status of the most recent request YOU created "
                "with request_staff_help this way. Use when Michael asks "
                "things like 'did maintenance see that' or 'any update'. "
                "Report only what this actually returns - never claim "
                "acknowledgment or completion it doesn't report."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "category": {
                        "type": "string",
                        "enum": ["nursing", "maintenance", "kitchen", "front_desk", "housekeeping", "complaint"],
                        "description": "Optional - narrow to one department's most recent request."
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
