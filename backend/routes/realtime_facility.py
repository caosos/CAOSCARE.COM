"""Facility time/location constants and "right now" helper.

Split out 2026-08-09 (part of the realtime.py 400-line cleanup) - shared
by realtime.py (_build_aria_instructions, route handlers) and
realtime_companion_prompt.py (_build_companion_instructions), which would
otherwise need to import from each other.
"""
import os
from datetime import datetime
from zoneinfo import ZoneInfo

FACILITY_LABEL = os.environ.get("FACILITY_LABEL") or "the facility"
FACILITY_TZ = os.environ.get("FACILITY_TZ") or "America/New_York"


def _facility_now() -> dict:
    """Returns a clean structured snapshot of "right now" at the facility.
    Without this the Realtime model defaults to UTC and greets residents with
    'good morning' at 7pm. This is also the anchor for time-aware tool calls
    (set_timer durations, story arcs, etc.)."""
    try:
        now = datetime.now(ZoneInfo(FACILITY_TZ))
    except Exception:
        now = datetime.utcnow()
    h = now.hour
    if 5 <= h < 12:
        part = "morning"
    elif 12 <= h < 17:
        part = "afternoon"
    elif 17 <= h < 21:
        part = "evening"
    else:
        part = "night"
    return {
        "iso": now.isoformat(),
        "weekday": now.strftime("%A"),
        "date": now.strftime("%B %-d, %Y"),
        "time": now.strftime("%-I:%M %p"),
        "part_of_day": part,
        "tz": FACILITY_TZ,
    }
