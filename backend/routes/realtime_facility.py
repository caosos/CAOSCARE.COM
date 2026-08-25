"""Facility time/location - "right now" helper plus the active-facility
lookup.

Split out 2026-08-09 (part of the realtime.py 400-line cleanup) - shared
by realtime.py (_build_aria_instructions, route handlers) and
realtime_companion_prompt.py (_build_companion_instructions), which would
otherwise need to import from each other.

2026-08-25: a real db.facilities record exists (Conway, AR) but was never
read here - this module only ever read FACILITY_LABEL/FACILITY_TZ from
.env, one of which was still a dev placeholder ("the EliteDesk node"),
which is why a resident had to tell Aria what city she was in. Voice now
prefers the live facility record; FACILITY_LABEL/FACILITY_TZ remain the
fallback when no facility record exists. today_facility_date() below is
intentionally left reading FACILITY_TZ only (unchanged, out of scope here)
- it is used by scheduling/menu/transportation date math elsewhere and
FACILITY_TZ is already correct (America/Chicago); this pass only fixes the
identity/location gap in the voice prompt path.
"""
import os
from datetime import datetime
from zoneinfo import ZoneInfo
from deps import db

FACILITY_LABEL = os.environ.get("FACILITY_LABEL") or "the facility"
FACILITY_TZ = os.environ.get("FACILITY_TZ") or "America/New_York"


async def get_active_facility() -> dict | None:
    """The single active facility record, if one exists. Single-community
    scope for now (matches the standing Admin blueprint) - no per-room/
    per-kiosk facility_id resolution yet, since there is exactly one."""
    return await db.facilities.find_one(
        {"is_active": True}, {"_id": 0}, sort=[("created_at", -1)],
    )


async def _facility_now() -> dict:
    """Returns a clean structured snapshot of "right now" at the facility,
    plus its identity (label/city/state/country) for the voice prompt to
    state directly rather than leaving a resident to supply their own city.
    Without the time anchor the Realtime model defaults to UTC and greets
    residents with 'good morning' at 7pm; it is also the anchor for
    time-aware tool calls (set_timer durations, story arcs, etc.)."""
    facility = await get_active_facility()
    tz_name = (facility or {}).get("timezone") or FACILITY_TZ
    try:
        now = datetime.now(ZoneInfo(tz_name))
    except Exception:
        tz_name = FACILITY_TZ
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
    label = (facility or {}).get("name") or FACILITY_LABEL
    city = (facility or {}).get("city")
    state = (facility or {}).get("state")
    country = (facility or {}).get("country")
    place = ", ".join(p for p in [city, state] if p) or None
    return {
        "iso": now.isoformat(),
        "weekday": now.strftime("%A"),
        "date": now.strftime("%B %-d, %Y"),
        "time": now.strftime("%-I:%M %p"),
        "part_of_day": part,
        "tz": tz_name,
        "label": label,
        "city": city,
        "state": state,
        "country": country,
        "place": place,
    }


def greeting_note(part_of_day: str) -> str:
    """How to phrase the opening greeting for this time of day. Split out
    2026-08-23: 'good night' as an OPENING greeting reads as a farewell -
    a real resident's first words back were "Why would you say goodbye to
    me?" 'night' stays valid for general time-of-day awareness elsewhere,
    just not as how the call opens."""
    if part_of_day == "night":
        return "greet warmly WITHOUT 'good night' (it reads as a farewell) - try 'I'm here' instead"
    return f"greet appropriately ('good {part_of_day}')"


def today_facility_date() -> str:
    """Facility-local YYYY-MM-DD - shared by any lane keyed on "today"
    (schedule, menu, ...) so a UTC day-rollover can't make something
    entered "for today" read as tomorrow's once the server's day changes
    ahead of the facility's own. Deliberately sync and FACILITY_TZ-only
    (not the facility-record-aware, async _facility_now() above) - many
    callers (scheduling/menu/transportation date math, seed scripts) need
    a plain sync call, and FACILITY_TZ is already correct (America/Chicago)
    so there is no bug here to fix this pass."""
    try:
        now = datetime.now(ZoneInfo(FACILITY_TZ))
    except Exception:
        now = datetime.utcnow()
    return now.strftime("%Y-%m-%d")
