"""Resident-facing tools for durable room interaction preferences."""


def _build_preference_tools() -> list[dict]:
    return [{
        "type": "function",
        "name": "set_tv_audio_duck",
        "description": (
            "Change whether this room automatically lowers TV/speaker volume while Aria is listening. "
            "This durable setting ALWAYS requires two calls. On the resident's first request, call with "
            "confirmed=false; the result gives the exact confirmation question. Only after the resident "
            "clearly answers yes/correct, call again with the same enabled value and confirmed=true. Never "
            "skip confirmation. If they decline or change their mind, do not call again."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "enabled": {"type": "boolean", "description": "true to lower and restore room audio automatically; false to leave it unchanged."},
                "confirmed": {"type": "boolean", "description": "false for the initial request; true only on the resident's later clear confirmation."},
            },
            "required": ["enabled", "confirmed"],
            "additionalProperties": False,
        },
    }]
