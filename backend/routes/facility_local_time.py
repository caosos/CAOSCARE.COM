"""Turn a raw UTC timestamp into what resident-facing Aria can say out loud,
in the facility's actual configured timezone (Level 1 directive 2026-09-07).

Uses the existing facility timezone truth: db.facilities.timezone, falling
back to FACILITY_TZ (already America/Chicago for Conway). Never hardcodes a
timezone; never manufactures a time - a missing timestamp returns None so
the caller says "I don't have that". Raw UTC is preserved for audit.
"""
from datetime import datetime
from typing import Optional
from zoneinfo import ZoneInfo

from routes.realtime_facility import get_active_facility, FACILITY_TZ


async def facility_tz() -> str:
    fac = await get_active_facility()
    return (fac or {}).get("timezone") or FACILITY_TZ


def facility_local(iso: Optional[str], tz: str) -> Optional[dict]:
    """{iso, local, label} for a UTC ISO string. `label` is a natural
    relative phrase: "today at 2:17 PM", "yesterday at 4:06 PM",
    "Monday at 2:17 PM", "September 3 at 2:17 PM". None if `iso` is falsy."""
    if not iso:
        return None
    try:
        dt = datetime.fromisoformat(iso)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=ZoneInfo("UTC"))
        local = dt.astimezone(ZoneInfo(tz))
        now_local = datetime.now(ZoneInfo(tz))
    except Exception:
        return {"iso": iso, "local": None, "label": None}
    days = (now_local.date() - local.date()).days
    t = local.strftime("%-I:%M %p")
    if days == 0:
        when = "today"
    elif days == 1:
        when = "yesterday"
    elif 2 <= days <= 6:
        when = local.strftime("%A")
    else:
        when = local.strftime("%B %-d")
    return {"iso": iso, "local": local.isoformat(), "label": f"{when} at {t}"}
