"""Resident-facing Realtime tool schemas for room-device control (smart-room
IoT: thermostat, TV, lights). Split out of realtime_tools.py 2026-08-27 -
that file was at the 300-line cap and this domain was about to grow (a
read tool was missing entirely: Aria had write tools for the thermostat/TV
but no way to answer "what's the temperature in here" without guessing).
Pure data, no FastAPI routes or DB access, same pattern as the sibling
realtime_tools_operations.py.
"""


def _build_device_tools() -> list[dict]:
    return [
        {
            "type": "function",
            "name": "get_room_status",
            "description": (
                "Read the REAL current state of the resident's room devices - "
                "thermostat reading/target and TV power/volume. Use this "
                "whenever they ask 'what's the temperature in here', 'is the "
                "TV on', or similar - answer ONLY from what this returns, "
                "never guess. Cheap to call."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
                "additionalProperties": False
            }
        },
        {
            "type": "function",
            "name": "adjust_room_temperature",
            "description": (
                "Control the resident's room air conditioner or thermostat: power, HVAC "
                "mode, or target temperature (absolute or relative). Only set the fields "
                "they actually asked about - e.g. 'turn the AC on' should set only state; "
                "'make it two degrees cooler' should set only delta_f. Setting mode or a "
                "temperature without state implies turning it on. Real devices vary in "
                "which modes they support - if the result says a mode or field isn't "
                "supported, tell the resident plainly rather than pretending it worked."
                " If the result says ambiguous (more than one in the room), do NOT call again yet: ASK the resident which one (the choices are listed), wait for their answer, then call again with device set to the exact choice. Never repeat the same call without a new answer."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "device": {
                        "type": "string",
                        "description": "Which one, only when the room has more than one of this device: its exact label or device_id (from an ambiguous result's choices)."
                    },
                    "state": {
                        "type": "string",
                        "enum": ["on", "off"],
                        "description": "Optional power state, e.g. 'turn the AC on/off'."
                    },
                    "mode": {
                        "type": "string",
                        "enum": ["cool", "heat", "auto", "fan_only"],
                        "description": "Optional HVAC mode, e.g. 'set it to cool'."
                    },
                    "target_f": {
                        "type": "number",
                        "minimum": 60,
                        "maximum": 85,
                        "description": "Optional absolute target temperature in Fahrenheit, e.g. 'set it to 72'."
                    },
                    "delta_f": {
                        "type": "number",
                        "minimum": -20,
                        "maximum": 20,
                        "description": "Optional relative temperature change when no exact number was given, e.g. -2 for 'make it two degrees cooler' or 'lower it a couple degrees', +2 for 'raise it two degrees'."
                    }
                },
                "additionalProperties": False
            }
        },
        {
            "type": "function",
            "name": "toggle_light",
            "description": (
                "Control the resident's room light: power, brightness, color, or "
                "white color temperature. Only set the fields the resident actually "
                "asked about - e.g. 'make it green' should set color WITHOUT state "
                "or brightness; 'turn it off' should set only state. Setting color, "
                "color_temp, or brightness without state implies turning it on. Not "
                "every light supports every field - if the result says a field "
                "isn't supported, tell the resident plainly rather than pretending. "
                "If the result says ambiguous (more than one light in the room), do NOT "
                "call again yet: ASK the resident which light (the choices are listed), "
                "wait for their answer, then call again with device set to the exact "
                "choice or device_id. Never repeat the same call without a new answer."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "state": {
                        "type": "string",
                        "enum": ["on", "off"],
                        "description": "Optional power state. Omit if only changing color/brightness on an already-on light."
                    },
                    "brightness": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 100,
                        "description": "Optional absolute brightness 1-100, e.g. 'set it to 50 percent'."
                    },
                    "brightness_delta": {
                        "type": "integer",
                        "minimum": -100,
                        "maximum": 100,
                        "description": "Optional relative brightness change when no exact percentage was given, e.g. -20 for 'dim it'/'make it dimmer', +20 for 'make it brighter'."
                    },
                    "color": {
                        "type": "string",
                        "enum": ["red", "orange", "yellow", "green", "blue", "purple", "pink", "white"],
                        "description": "Optional named color, e.g. 'make it green' or 'make it blue'."
                    },
                    "device": {
                        "type": "string",
                        "description": "Which light, only when the room has more than one: its exact label or device_id (from an ambiguous result's choices)."
                    },
                    "color_temp": {
                        "type": "string",
                        "enum": ["warm", "neutral", "cool"],
                        "description": "Optional white tone for 'warm white', 'cool white', or 'daylight' requests. Mutually exclusive with color."
                    }
                },
                "additionalProperties": False
            }
        },
        {
            "type": "function",
            "name": "toggle_tv",
            "description": (
                "Turn the resident's TV on or off, or set an exact volume. "
                "If the resident asks for quiet or to mute the TV, use action='off' "
                "or set volume to 0. For 'a little louder/quieter' use adjust_tv_volume; "
                "for a channel use set_tv_channel."
                " If the result says ambiguous (more than one in the room), do NOT call again yet: ASK the resident which one (the choices are listed), wait for their answer, then call again with device set to the exact choice. Never repeat the same call without a new answer."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "device": {
                        "type": "string",
                        "description": "Which one, only when the room has more than one of this device: its exact label or device_id (from an ambiguous result's choices)."
                    },
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
            "name": "adjust_tv_volume",
            "description": (
                "Turn the TV volume up or down by a step when the resident says "
                "'turn it up', 'a bit quieter', 'louder'. Only call this when they "
                "actually asked about volume or loudness. For an exact level they "
                "named, use toggle_tv with volume instead."
                " If the result says ambiguous (more than one in the room), do NOT call again yet: ASK the resident which one (the choices are listed), wait for their answer, then call again with device set to the exact choice. Never repeat the same call without a new answer."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "device": {
                        "type": "string",
                        "description": "Which one, only when the room has more than one of this device: its exact label or device_id (from an ambiguous result's choices)."
                    },
                    "direction": {"type": "string", "enum": ["up", "down"]},
                    "amount": {
                        "type": "integer", "minimum": 1, "maximum": 50,
                        "description": "Optional step in volume points (default 10)."
                    }
                },
                "required": ["direction"],
                "additionalProperties": False
            }
        },
        {
            "type": "function",
            "name": "set_tv_channel",
            "description": (
                "Change the TV to a channel number the resident said ('put on "
                "channel 11'). Use the number they said; never guess one. If the "
                "result says the TV has no channel control, tell them plainly."
                " If the result says ambiguous (more than one in the room), do NOT call again yet: ASK the resident which one (the choices are listed), wait for their answer, then call again with device set to the exact choice. Never repeat the same call without a new answer."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "device": {
                        "type": "string",
                        "description": "Which one, only when the room has more than one of this device: its exact label or device_id (from an ambiguous result's choices)."
                    },
                    "channel": {"type": "integer", "minimum": 1, "maximum": 999}
                },
                "required": ["channel"],
                "additionalProperties": False
            }
        },
        {
            "type": "function",
            "name": "set_blinds",
            "description": (
                "Open, close, or set the room's blinds when the resident asks about "
                "blinds, shades or curtains. action='open' = fully open, 'close' = "
                "fully closed, 'set' = a percent open (0 closed - 100 open). If the "
                "result says the room has no blinds, say so plainly."
                " If the result says ambiguous (more than one in the room), do NOT call again yet: ASK the resident which one (the choices are listed), wait for their answer, then call again with device set to the exact choice. Never repeat the same call without a new answer."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "device": {
                        "type": "string",
                        "description": "Which one, only when the room has more than one of this device: its exact label or device_id (from an ambiguous result's choices)."
                    },
                    "action": {"type": "string", "enum": ["open", "close", "set"]},
                    "percent": {
                        "type": "integer", "minimum": 0, "maximum": 100,
                        "description": "Required when action='set': how far open."
                    }
                },
                "required": ["action"],
                "additionalProperties": False
            }
        },
        {
            "type": "function",
            "name": "set_tv_input",
            "description": (
                "Switch the resident's TV to a different input/source (e.g. "
                "'switch to HDMI 2', 'put it on the antenna'). Only call this if "
                "get_room_status showed the TV has an 'input' capability with a "
                "matching option in its inputs list - if the device doesn't list "
                "that input, tell the resident plainly it isn't available rather "
                "than calling this and letting it fail silently."
                " If the result says ambiguous (more than one in the room), do NOT call again yet: ASK the resident which one (the choices are listed), wait for their answer, then call again with device set to the exact choice. Never repeat the same call without a new answer."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "device": {
                        "type": "string",
                        "description": "Which one, only when the room has more than one of this device: its exact label or device_id (from an ambiguous result's choices)."
                    },
                    "input": {
                        "type": "string",
                        "description": "The exact input name as listed in the device's own `inputs`, e.g. 'HDMI 2'."
                    }
                },
                "required": ["input"],
                "additionalProperties": False
            }
        },
    ]
