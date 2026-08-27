"""Resident-facing Realtime tool schema for the resident's own display/
accessibility setting (screen magnification). Split into its own file
2026-08-27 rather than folded into realtime_device_tools.py (room hardware)
or realtime_tools_operations.py (staff request bus) - a display preference
is neither, and this domain is likely to grow (voice-controlled contrast,
voice, etc. could join it later without bloating an unrelated file).

Generalizes/replaces the kiosk's old fixed 3-step text-size cycle (md/lg/xl,
via hand-picked CSS selectors that only covered the greeting/buttons) with a
continuous, bounded percentage applied at the document root - covers the
whole resident screen, including panels that didn't exist when the old
mechanism was written, and is the one thing both Aria and the on-screen
+/- control update (see frontend/src/lib/useMagnification.js).
"""

MIN_MAGNIFICATION = 50
MAX_MAGNIFICATION = 200


def _build_display_tools() -> list[dict]:
    return [
        {
            "type": "function",
            "name": "set_magnification",
            "description": (
                "Change how large the resident's screen text/interface appears. "
                "Use for 'make this bigger', 'make it smaller', 'magnification "
                "mode 150%', 'go back to normal size', 'make my maintenance "
                "request bigger' (there's no per-item zoom - this changes the "
                "whole screen, which covers that ask). Pass `percent` for an "
                "exact size the resident stated (e.g. 150 or 50); pass "
                "`direction` instead for a relative request with no number. "
                "After calling, briefly confirm in one short sentence."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "percent": {
                        "type": "integer",
                        "minimum": MIN_MAGNIFICATION,
                        "maximum": MAX_MAGNIFICATION,
                        "description": "Exact size percentage, if the resident gave one."
                    },
                    "direction": {
                        "type": "string",
                        "enum": ["bigger", "smaller", "reset"],
                        "description": "Relative change, if no exact percentage was given."
                    }
                },
                "additionalProperties": False
            }
        },
    ]
