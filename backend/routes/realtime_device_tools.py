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
            "name": "set_tv_input",
            "description": (
                "Switch the resident's TV to a different input/source (e.g. "
                "'switch to HDMI 2', 'put it on the antenna'). Only call this if "
                "get_room_status showed the TV has an 'input' capability with a "
                "matching option in its inputs list - if the device doesn't list "
                "that input, tell the resident plainly it isn't available rather "
                "than calling this and letting it fail silently."
            ),
            "parameters": {
                "type": "object",
                "properties": {
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
