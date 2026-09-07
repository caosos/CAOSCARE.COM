"""Pure parse/format helpers for routes/ops_overview.py - split out so the
aggregation handler stays under the file-size cap. No DB, no state.
"""
from datetime import datetime, timezone
from typing import Optional
from zoneinfo import ZoneInfo

from routes.realtime_facility import FACILITY_TZ

EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)


def parse_dt(v) -> Optional[datetime]:
    if not v:
        return None
    try:
        dt = datetime.fromisoformat(v) if isinstance(v, str) else v
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except Exception:
        return None


def age_seconds(v, now: datetime) -> Optional[int]:
    dt = parse_dt(v)
    return int((now - dt).total_seconds()) if dt else None


def local_date(v) -> Optional[str]:
    """Facility-local YYYY-MM-DD for a stored (UTC) timestamp."""
    dt = parse_dt(v)
    if not dt:
        return None
    try:
        return dt.astimezone(ZoneInfo(FACILITY_TZ)).strftime("%Y-%m-%d")
    except Exception:
        return None


def dept_label(vis_role: Optional[str], by_slug: dict) -> str:
    if not vis_role or vis_role == "all_staff":
        return "General / all-staff"
    d = by_slug.get(vis_role)
    return d["label"] if d else vis_role


def task_link_hint(t: dict) -> str:
    """Which admin surface should open this task: transportation calendar,
    the Requests board (resident/family/Aria/front-desk originated), or the
    staff Tasks board (an internal chore)."""
    if t.get("category") == "transportation":
        return "transportation"
    if (t.get("source") or "staff") != "staff":
        return "requests"
    return "tasks"


def short_duration(seconds: float) -> str:
    s = int(seconds)
    if s < 3600:
        return f"{max(1, s // 60)}m"
    if s < 86400:
        return f"{s // 3600}h"
    return f"{s // 86400}d"
