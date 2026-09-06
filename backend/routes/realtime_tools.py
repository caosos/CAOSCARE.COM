"""Resident-facing Realtime tool schemas (function-calling definitions
the model can invoke during a live conversation).

Split out of realtime.py 2026-08-09 (was pushing that file well past the
400-line code-file cap). Pure data, no FastAPI routes or DB access. See
the sibling realtime_self_knowledge.py for the "about yourself" block,
realtime_tools_operations.py (split out 2026-08-10, same reason) for the
operational request-bus tools: staff requests, transportation, schedule,
menu; realtime_device_tools.py (split out 2026-08-27, same reason) for
room-device control: thermostat, TV, lights; and realtime_display_tools.py
(added 2026-08-27) for the resident's own display/magnification setting.
"""
from routes.realtime_tools_operations import _build_operations_tools
from routes.realtime_device_tools import _build_device_tools
from routes.realtime_display_tools import _build_display_tools
from routes.resident_requests import get_request_categories


async def _build_tools() -> list[dict]:
    """Tool surface CAOS can invoke during a live conversation.

    Each tool maps to a public backend endpoint the frontend will call when
    the model emits a `function_call`. Keeping descriptions tight and
    parameters strictly typed forces the model to choose deterministically
    instead of hallucinating arguments.

    Async since 2026-08-10 - the request-category enum is now a live query
    against the admin-managed Department list instead of a fixed tuple, so
    a newly-added department is usable by Aria the moment it's created.
    """
    return _build_device_tools() + [
        {
            "type": "function",
            "name": "call_for_help",
            "description": (
                "Escalate to a caregiver IMMEDIATELY when the resident describes "
                "chest pain, breathing trouble, a fall, severe dizziness, confusion, "
                "or directly asks for a nurse. Do NOT use for casual conversation. "
                "Do NOT use for a routine bathroom/toileting/mobility-assistance "
                "need - that is request_staff_help (nursing, priority='high'), not "
                "an emergency-tier escalation, even though it should still be fast. "
                "After calling, reassure the resident that help is on the way and "
                "stay with them."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "reason": {
                        "type": "string",
                        "description": "One short sentence summarising what the resident said."
                    },
                    "severity": {
                        "type": "string",
                        "enum": ["assist", "emergency"],
                        "description": "'emergency' for chest pain/fall/breathing; 'assist' otherwise."
                    }
                },
                "required": ["reason", "severity"],
                "additionalProperties": False
            }
        },
        {
            "type": "function",
            "name": "mark_resting",
            "description": (
                "Call this ONLY for a CLEAR, explicit dismissal: 'be quiet', 'stop "
                "talking', 'let me rest', 'I'm going to sleep', 'not now'. Do NOT call "
                "this for ambiguous statements, frustration, or comments about volume/"
                "hearing/technical trouble (e.g. 'turn it up', 'I can't hear you') - "
                "those are NOT a request to go quiet. You have no control over your "
                "own voice volume; if asked to speak up or turn yourself up, say so "
                "plainly instead of going quiet. When unsure whether this is a real "
                "dismissal, do not call it - keep talking normally. After calling, "
                "stop talking. Do NOT begin a new turn until they speak again."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "reason": {
                        "type": "string",
                        "description": "Why they're resting (sleep / quiet time / other)."
                    }
                },
                "required": [],
                "additionalProperties": False
            }
        },
        {
            "type": "function",
            "name": "request_live_staff",
            "description": (
                "Use ONLY when a help-button press already brought you into this "
                "conversation (there is an open event) AND the resident now asks for "
                "a nurse/staff/someone by name. Do NOT use this for a brand-new "
                "symptom with no prior button press - use call_for_help for that "
                "instead. Calling this may ask the resident one routing question "
                "('someone in the room right now, or talk to me until they get "
                "here?') - if so, wait for their next reply and call this again with "
                "what they said. Never ask that question twice for the same request."
            ),
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False}
        },
        {
            "type": "function",
            "name": "get_current_time",
            "description": (
                "Get the current local date, weekday, time, and part of day at the "
                "resident's facility. Use whenever the resident asks 'what time is it', "
                "'what day is it', 'how long until dinner', or seems disoriented "
                "about the time. Cheap to call — prefer this over guessing."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
                "additionalProperties": False
            }
        },
        {
            "type": "function",
            "name": "get_weather",
            "description": (
                "Get the current weather and today's forecast for the facility (or "
                "another city if the resident asks). Use when they ask about weather, "
                "whether to wear a sweater, if it'll rain, etc. Returns a short "
                "spoken-friendly summary you should read aloud naturally."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {
                        "type": "string",
                        "description": (
                            "Optional city / region name. Leave empty for the facility's "
                            "own location. Use the resident's hometown if they ask about "
                            "'home' or where their family lives."
                        )
                    }
                },
                "required": [],
                "additionalProperties": False
            }
        },
        {
            "type": "function",
            "name": "research_topic",
            "description": (
                "Look up real-world information on the live web — current events, news, "
                "sports scores, history, recipes, prayers, biographies, anything. Use "
                "freely whenever the resident asks a factual question you cannot answer "
                "from memory. After getting the result, read it aloud naturally — do "
                "NOT just dump the text. Speak like a friend who just read about it."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "question": {
                        "type": "string",
                        "description": "The question to research, in plain English."
                    }
                },
                "required": ["question"],
                "additionalProperties": False
            }
        },
        {
            "type": "function",
            "name": "set_timer",
            "description": (
                "Set a one-shot timer that will speak a reminder when it's due. Use "
                "for things like 'remind me to take my pills in 20 minutes', 'wake me "
                "up in 30', 'tell me when it's been an hour'. The kiosk will speak "
                "the label aloud at that time. After calling, confirm in one sentence."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "minutes": {
                        "type": "number",
                        "minimum": 0.1,
                        "maximum": 720,
                        "description": "Number of minutes from now (max 720 = 12 hours)."
                    },
                    "label": {
                        "type": "string",
                        "description": "Short reminder text the kiosk will speak when due."
                    }
                },
                "required": ["minutes", "label"],
                "additionalProperties": False
            }
        },
        {
            "type": "function",
            "name": "update_preferred_name",
            "description": (
                "Call this IMMEDIATELY when the resident corrects what you call them "
                "(e.g., 'my name is Margaret, not Maggie' or 'call me Mags'). This "
                "permanently updates the name you use for them — across this call AND "
                "every future call. After calling, apologize once briefly ('You're "
                "right, sorry — Margaret it is') and use the new name from then on. "
                "Do NOT keep using the old name after the resident has corrected you."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "preferred_name": {
                        "type": "string",
                        "description": "The exact name the resident asked to be called."
                    }
                },
                "required": ["preferred_name"],
                "additionalProperties": False
            }
        },
        {
            "type": "function",
            "name": "end_call",
            "description": (
                "End the voice call and hang up. Call this whenever the resident says "
                "'end the call', 'hang up', 'goodbye', 'I'm done', 'that's all', or "
                "otherwise clearly wants the conversation OVER (different from "
                "`mark_resting`, which just goes quiet but stays connected). After "
                "calling, say one short warm goodbye and then stop talking — the kiosk "
                "will tear down the connection."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "reason": {
                        "type": "string",
                        "description": "Why they ended (done / goodbye / staff arrived / other)."
                    }
                },
                "required": [],
                "additionalProperties": False
            }
        },
    ] + _build_operations_tools(await get_request_categories()) + _build_display_tools()


