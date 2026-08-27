"""Resident-facing Realtime tool schemas for the operational request bus:
staff requests, transportation, schedule, menu. Split out of
realtime_tools.py 2026-08-10 (was pushing that file past the 400-line
code-file cap) - pure data, no FastAPI routes or DB access, same as the
sibling it was split from.
"""

# Fallback if the caller doesn't pass a live category list (defensive
# only - realtime_tools.py always passes the real one from
# routes/departments.py + resident_requests.py's aliases).
_DEFAULT_REQUEST_CATEGORIES = ["nursing", "maintenance", "kitchen", "front_desk", "housekeeping", "complaint"]


def _build_operations_tools(request_categories: list[str] | None = None) -> list[dict]:
    categories = request_categories or _DEFAULT_REQUEST_CATEGORIES
    return [
        {
            "type": "function",
            "name": "request_staff_help",
            "description": (
                "Create a real, NON-EMERGENCY request routed to the right staff "
                "department - pick whichever category in the enum best matches "
                "what the resident needs (nursing for private/clinical concerns "
                "or wanting to talk to a nurse, maintenance for something broken, "
                "etc.). Use call_for_help instead for anything urgent/medical/"
                "emergency. After calling this, "
                "tell the resident the request was CREATED and sent - do not say "
                "someone is already coming or already spoke to them unless "
                "check_request_status confirms it. If the result says an open "
                "request already existed (duplicate/re_request_count), tell the "
                "resident honestly that it was already on file and you've let "
                "staff know again - do not claim a brand-new request was made. "
                "If that result's same_issue is false, the open ticket is about "
                "something ELSE in the same department (see existing_summary) - "
                "say what THAT is actually about, do not describe it as if it "
                "matches what the resident just asked for. "
                "`summary` must ONLY contain details the resident actually said "
                "this call (or a tool result confirmed) - never add a time, date, "
                "or other specific you inferred or guessed. If a detail like a "
                "time genuinely matters and the resident didn't give one, ask "
                "them for it before calling this - do not fill it in yourself."
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
                        "description": "Short, concrete summary of what's needed, in the resident's own terms where possible."
                    },
                    "priority": {
                        "type": "string",
                        "enum": ["low", "normal", "high", "urgent"],
                        "description": "Default 'normal' unless the resident indicates real urgency (but not emergency-level - use call_for_help for that)."
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
                "Check the real status of the resident's most recent staff request "
                "(from request_staff_help). Use this when they ask things like 'did "
                "the nurse see my message', 'is anyone coming for the light', 'what "
                "did I call maintenance about', or 'when are they coming'. The result "
                "includes `what_for` (say plainly what the request is actually about - "
                "never just say 'a maintenance request'), `scheduled_date`/"
                "`scheduled_time_label` (a REAL staff-entered planned visit window - "
                "report it if present; if BOTH are empty, say there is no scheduled "
                "time yet - never invent an ETA), and `latest_update` (a staff note, "
                "e.g. waiting on a part - read it aloud if present). Report only what "
                "this actually returns - never say someone is on the way unless "
                "status is acknowledged/in_progress, and never say it's done unless "
                "status is completed."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "category": {
                        "type": "string",
                        "enum": categories,
                        "description": "Optional - narrow to one department's most recent request."
                    }
                },
                "additionalProperties": False
            }
        },
        {
            "type": "function",
            "name": "check_transportation_availability",
            "description": (
                "Check real transportation slot availability for a date - "
                "use before promising a ride time. Returns real open/full "
                "times. You may say 'there's an opening at 10' from this - "
                "you may NOT say a ride is booked from this alone, only "
                "that a slot exists."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "date": {"type": "string", "description": "YYYY-MM-DD. Leave empty for today."}
                },
                "additionalProperties": False
            }
        },
        {
            "type": "function",
            "name": "request_transportation",
            "description": (
                "Request a ride for the resident - use for pharmacy, "
                "doctor, shopping, family visits, etc. If they gave a "
                "future day ('Thursday', 'tomorrow') resolve it to a real "
                "YYYY-MM-DD yourself from the current facility date you "
                "were given - never treat a future request as 'now'. If "
                "you checked availability and know an open start_time, "
                "pass it to actually reserve that slot. After calling: if "
                "the result says booked, say it's confirmed for that time. "
                "If not booked, say the request was submitted and you "
                "don't have a confirmed time yet - do NOT say 'booked' "
                "unless the result says booked=true. `requested_for_time_label` "
                "must be the time AS THE RESIDENT SAID IT, or omitted entirely "
                "if they never gave one - never invent a specific time."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "purpose": {"type": "string", "description": "e.g. 'pharmacy pickup', 'doctor appointment', 'grocery shopping'."},
                    "requested_for_date": {"type": "string", "description": "YYYY-MM-DD, resolved from what the resident said."},
                    "requested_for_time_label": {"type": "string", "description": "The time as the resident said it, e.g. 'around 10' or 'after lunch'."},
                    "start_time": {"type": "string", "description": "Exact 'HH:00' 24h if you confirmed a specific open slot via check_transportation_availability."}
                },
                "required": ["purpose", "requested_for_date"],
                "additionalProperties": False
            }
        },
        {
            "type": "function",
            "name": "check_transportation_status",
            "description": (
                "Check the real status of the resident's most recent open "
                "transportation request - use for 'did anyone see my ride "
                "request' or 'am I booked yet'. Report only what this "
                "returns - never claim booked unless booked=true."
            ),
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False}
        },
        {
            "type": "function",
            "name": "change_transportation_request",
            "description": (
                "Change the resident's existing open transportation "
                "request to a different date/time - use for 'make it "
                "Friday instead' or 'can we move it to the afternoon'. "
                "Resolves the request from context - no ID needed."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "requested_for_date": {"type": "string", "description": "New YYYY-MM-DD."},
                    "requested_for_time_label": {"type": "string", "description": "New time as the resident said it."},
                    "start_time": {"type": "string", "description": "Exact 'HH:00' if a specific open slot was confirmed."}
                },
                "required": ["requested_for_date"],
                "additionalProperties": False
            }
        },
        {
            "type": "function",
            "name": "cancel_transportation_request",
            "description": (
                "Cancel the resident's existing open transportation "
                "request - use for 'I don't need that ride anymore'."
            ),
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False}
        },
        {
            "type": "function",
            "name": "get_todays_schedule",
            "description": (
                "Get today's real activities/facility schedule - things like what "
                "activity is happening, when the AC or another facility system is "
                "off for maintenance, or general 'what's going on today' questions. "
                "Answer ONLY from what this returns. If it comes back empty, say "
                "honestly that nothing is listed for today yet - never invent an "
                "activity or time. This is not for staff on-duty hours or requests - "
                "just the resident-facing daily schedule."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
                "additionalProperties": False
            }
        },
        {
            "type": "function",
            "name": "get_menu",
            "description": (
                "Get the real, staff-approved menu - use when the resident "
                "asks what's for breakfast, lunch, dinner, or uses equivalent "
                "words: 'supper' and 'evening meal' both mean dinner, 'morning "
                "meal' means breakfast, 'noon meal' means lunch - always pass "
                "the canonical meal_period value, never the resident's own "
                "words. Answer ONLY from what this returns - NEVER guess or "
                "invent a dish or use general knowledge. If it comes back "
                "empty for that meal period, say honestly that you don't have "
                "that menu yet - do not make one up. This matters especially "
                "for dietary/diabetic questions - never state a food is or "
                "isn't on the menu unless this tool actually confirms it."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "meal_period": {
                        "type": "string",
                        "enum": ["breakfast", "lunch", "dinner"],
                        "description": "Which meal. Leave empty to get everything approved for that date."
                    },
                    "date": {
                        "type": "string",
                        "description": "YYYY-MM-DD. Leave empty for today. Compute 'tomorrow' yourself from the current facility date/time you were given."
                    }
                },
                "additionalProperties": False
            }
        },
    ]
