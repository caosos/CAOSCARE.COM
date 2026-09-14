"""Realtime tool schema for confirming a person-specific interpretation
pattern (Terminal 10). Split out, same convention as
realtime_tools_operations.py / realtime_display_tools.py - pure data, no
FastAPI routes or DB access (those live in aria_interpretation_patterns.py).
"""


def _build_interpretation_tools() -> list[dict]:
    return [
        {
            "type": "function",
            "name": "confirm_interpretation_pattern",
            "description": (
                "Record a CONFIRMED person-specific interpretation pattern - use "
                "this when you had to work out what the resident meant from an "
                "imperfect, phonetic, shorthand, or language-learning phrase, AND "
                "the resident confirmed your understanding was right (directly, "
                "or by continuing naturally as if you understood correctly). "
                "Example: they say 'dos savor', you understand 'dos sabores' "
                "(two flavors), they confirm - call this so the SAME phrase is "
                "understood correctly next time, in this or a future call. "
                "Do NOT call this for a one-off misheard word with no real "
                "pattern, and do NOT call this just because you asked a "
                "clarifying question - only when there is a genuine, confirmed "
                "person-specific pattern worth remembering. `heard_as` must be "
                "the resident's own words, not your corrected version."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "heard_as": {
                        "type": "string",
                        "description": "Exactly what the resident said, in their own words.",
                    },
                    "understood_as": {
                        "type": "string",
                        "description": "The corrected/natural form you understood it as.",
                    },
                    "meaning": {
                        "type": "string",
                        "description": "Plain-language meaning, e.g. an English translation, if relevant.",
                    },
                    "language": {
                        "type": "string",
                        "description": "ISO-639-1 code of `understood_as`, e.g. 'es'. Omit if not language-related.",
                    },
                    "category": {
                        "type": "string",
                        "enum": ["phonetic", "shorthand", "substitution", "language_learning", "other"],
                        "description": "What kind of pattern this is.",
                    },
                },
                "required": ["heard_as", "understood_as"],
                "additionalProperties": False,
            },
        },
    ]
