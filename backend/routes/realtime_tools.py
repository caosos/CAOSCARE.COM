"""Resident-facing Realtime tool schemas (function-calling definitions
the model can invoke during a live conversation).

Split out of realtime.py 2026-08-09 (was pushing that file well past the
400-line code-file cap). Pure data, no FastAPI routes or DB access. See
the sibling realtime_self_knowledge.py for the "about yourself" block.
"""


def _build_tools() -> list[dict]:
    """Tool surface CAOS can invoke during a live conversation.

    Each tool maps to a public backend endpoint the frontend will call when
    the model emits a `function_call`. Keeping descriptions tight and
    parameters strictly typed forces the model to choose deterministically
    instead of hallucinating arguments.
    """
    return [
        {
            "type": "function",
            "name": "adjust_room_temperature",
            "description": (
                "Set the air conditioning or heater target temperature in the resident's "
                "room. Use ONLY when the resident clearly asks to be warmer or cooler. "
                "After calling, briefly confirm what you did in one short sentence."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "target_f": {
                        "type": "number",
                        "minimum": 60,
                        "maximum": 85,
                        "description": "Target temperature in Fahrenheit (60-85)."
                    },
                    "mode": {
                        "type": "string",
                        "enum": ["cool", "heat", "auto"],
                        "description": "Whether to cool or heat. Default 'auto' if uncertain."
                    }
                },
                "required": ["target_f"],
                "additionalProperties": False
            }
        },
        {
            "type": "function",
            "name": "toggle_light",
            "description": (
                "Turn the resident's room light on or off, or set its brightness. "
                "Use when they ask for the light or for it to be brighter/dimmer."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "state": {
                        "type": "string",
                        "enum": ["on", "off"],
                        "description": "Whether to turn the light on or off."
                    },
                    "brightness": {
                        "type": "integer",
                        "minimum": 0,
                        "maximum": 100,
                        "description": "Optional brightness 0-100. Omit for full on."
                    }
                },
                "required": ["state"],
                "additionalProperties": False
            }
        },
        {
            "type": "function",
            "name": "toggle_tv",
            "description": (
                "Turn the resident's TV on or off, change channel, or adjust volume. "
                "If the resident asks for quiet or to mute the TV, use action='off' "
                "or set volume to 0."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "state": {
                        "type": "string",
                        "enum": ["on", "off"],
                        "description": "Power state for the TV."
                    },
                    "volume": {
                        "type": "integer",
                        "minimum": 0,
                        "maximum": 100,
                        "description": "Optional volume 0-100."
                    }
                },
                "required": ["state"],
                "additionalProperties": False
            }
        },
        {
            "type": "function",
            "name": "call_for_help",
            "description": (
                "Escalate to a caregiver IMMEDIATELY when the resident describes "
                "chest pain, breathing trouble, a fall, severe dizziness, confusion, "
                "or directly asks for a nurse. Do NOT use for casual conversation. "
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
            "name": "request_staff_help",
            "description": (
                "Create a real, NON-EMERGENCY request routed to the right staff "
                "department - nursing (private/clinical concerns, wanting to talk "
                "to a nurse), maintenance (something broken - light, AC, TV, "
                "plumbing), kitchen (a food/meal issue), housekeeping, front_desk "
                "(general front-desk needs), or complaint. Use call_for_help "
                "instead for anything urgent/medical/emergency. After calling this, "
                "tell the resident the request was CREATED and sent - do not say "
                "someone is already coming or already spoke to them unless "
                "check_request_status confirms it."
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
                "the nurse see my message' or 'is anyone coming for the light'. "
                "Report only what this actually returns - never say someone is on "
                "the way unless status is acknowledged/in_progress, and never say "
                "it's done unless status is completed."
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
            "name": "mark_resting",
            "description": (
                "Call this when the resident asks you to be quiet, says they want to rest, "
                "are going to sleep, or otherwise dismisses the conversation. After this, "
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
    ]


