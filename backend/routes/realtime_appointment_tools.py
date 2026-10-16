"""Realtime tool schemas for outside appointments (routes/appointments.py).
The browser relays them (frontend realtimeAppointmentTools.js). Aria speaks
the backend's `spoken` line, which already says what is verified, what is
only reported and where any discrepancy is."""


def _build_appointment_tools() -> list[dict]:
    return [
        {
            "type": "function",
            "name": "check_appointment",
            "description": (
                "Use when the resident asks about an outside appointment (doctor, dentist, "
                "cardiologist, eye doctor, a clinic) and has not just told you its day or time: 'what "
                "time is my appointment?', 'is that "
                "appointment definitely tomorrow?', 'did my doctor change it?', 'do I have a ride for "
                "it?'. If they tell you a day or time, use note_reported_appointment instead. It reads the appointment record and its sources. Speak from its `spoken` line: "
                "it says whether the time is verified (and by what), only reported, in conflict, "
                "changed or cancelled. Never state an appointment time or day that this result does "
                "not give, never round an unverified time into a definite one, and never say an "
                "office was called or confirmed anything unless the result says so. Therapy and "
                "other appointments inside the community come from get_todays_schedule / "
                "check_request_status instead."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "about": {"type": "string", "description": "Which appointment, in their words: 'cardiologist', 'Dr. Patel', 'eye doctor'. Empty if they just said 'my appointment'."},
                    "date": {"type": "string", "description": "YYYY-MM-DD only if they named a day ('tomorrow', 'Tuesday'), resolved from the current facility date."},
                    "focus": {"type": "string", "enum": ["general", "time", "date", "change", "ride"],
                              "description": "time = what time; date = is it definitely that day; change = did it change; ride = do I have a ride."},
                },
                "required": [],
                "additionalProperties": False,
            },
        },
        {
            "type": "function",
            "name": "note_reported_appointment",
            "description": (
                "Call this straight away whenever the resident TELLS you an outside appointment's day "
                "or time, even unsure ('I think my cardiologist is Tuesday at 10', 'I see the dentist "
                "on the 21st') - do not call check_appointment first and do not ask them to repeat "
                "it; this tool also checks what is on file. It records what "
                "they said as REPORTED - never verified - and compares it with any confirmation on "
                "file. Say its `spoken` line: if a confirmation disagrees, it gives the verified time "
                "and the difference. Resolve the day to a real YYYY-MM-DD from the current facility "
                "date; if they gave only a day of the month, say the full date back with weekday and "
                "month and wait for a yes first. Pass `time` only if they said a time - never "
                "invent one."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "provider": {"type": "string", "description": "Who or what: 'cardiologist', 'Dr. Patel', 'dentist'."},
                    "date": {"type": "string", "description": "YYYY-MM-DD."},
                    "time": {"type": "string", "description": "HH:MM 24h, only if they said a time."},
                    "time_as_said": {"type": "string", "description": "The time exactly as they said it, e.g. 'at 10', 'around ten thirty'."},
                    "location": {"type": "string", "description": "Where, only if they said."},
                    "resident_words": {"type": "string", "description": "What they said, in their own words."},
                    "says_changed": {"type": "boolean", "description": "True when they say the appointment was moved ('they changed it to Thursday'). It is still only reported."},
                },
                "required": ["date"],
                "additionalProperties": False,
            },
        },
    ]
