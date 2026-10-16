"""Realtime tool schema for the medication-status path
(routes/medication_status.py). Kept apart from realtime_tools.py so that
file does not grow; the browser relays it (frontend realtimeMedicationTool.js)."""


def _build_medication_tools() -> list[dict]:
    return [{
        "type": "function",
        "name": "check_medication_status",
        "description": (
            "Use when the resident says a medication is late, missed, or asks whether someone "
            "is coming with their medicine ('it's 6:03 and I was supposed to get my medicine at "
            "six - is someone coming?'). It checks today's medication schedule and any nursing "
            "request already open, reports only what staff have actually confirmed, and when "
            "nothing is confirmed it sends a HIGH-priority request to nursing itself - do not "
            "also call request_staff_help. Speak from its `spoken` line. A reminder is not proof "
            "anyone is coming: never say someone is coming or on the way. Never advise on the "
            "medication itself."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "resident_words": {
                    "type": "string",
                    "description": "What the resident said, in their own words.",
                },
            },
            "required": [],
            "additionalProperties": False,
        },
    }]
