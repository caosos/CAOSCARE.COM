"""Simple, resident-specific historical notation (2026-09-06 directive) -
deliberately NOT a black-box risk score. Bucketed by hour-of-day, same
"pull + filter in Python" precedent as insights.py::_count_alerts (Mongo's
string-stored dates can't do server-side hour extraction). Stats are only
ever recomputed AFTER an event closes (called from routes/alerts.py), and
a footnote is only produced once a bucket has
ResidentAssistanceConfig.pattern_min_events - otherwise "Not enough
history." Patterns are read-only footnotes: nothing here may suppress,
delay, or otherwise gate an activation - see record_resident_activation()
in resident_activation.py, which is the only thing that ever CREATES or
coalesces an event.
"""
import logging
import statistics
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends

from deps import db, require_admin

router = APIRouter(prefix="/resident-patterns", tags=["resident-patterns"])
log = logging.getLogger(__name__)

DEFAULT_MIN_EVENTS = 5


async def _min_events(facility_id: Optional[str] = None) -> int:
    cfg = await db.resident_assistance_config.find_one({"facility_id": facility_id}, {"_id": 0, "pattern_min_events": 1})
    return (cfg or {}).get("pattern_min_events", DEFAULT_MIN_EVENTS)


def _bucket_for(created_at_iso: str) -> str:
    return str(datetime.fromisoformat(created_at_iso).hour)


async def footnote_for_resident_now(resident_id: str) -> Optional[str]:
    bucket = str(datetime.now().hour)
    pattern = await db.resident_button_patterns.find_one(
        {"resident_id": resident_id, "bucket": bucket}, {"_id": 0},
    )
    if not pattern or pattern.get("n_events", 0) < await _min_events():
        return None
    lo = pattern.get("typical_press_count_p50")
    hi = pattern.get("typical_press_count_p90")
    if lo is None or hi is None:
        return "Not enough history"
    return f"This hour: usually {round(lo)}-{round(hi)} presses"


async def update_pattern_stats(resident_id: str, closed_alert: dict) -> None:
    """Recompute one resident+bucket's stats from all of their closed
    alerts in that bucket. Called after routes/alerts.py resolves/closes
    an alert - never on open/create, per the directive."""
    created_at = closed_alert.get("created_at")
    if not created_at:
        return
    bucket = _bucket_for(created_at)

    closed = await db.alerts.find(
        {"resident_id": resident_id, "status": "resolved"},
        {"_id": 0, "created_at": 1, "resolved_at": 1, "press_count": 1, "category": 1},
    ).to_list(500)
    same_bucket = [c for c in closed if c.get("created_at") and _bucket_for(c["created_at"]) == bucket]
    if not same_bucket:
        return

    press_counts = [c.get("press_count", 1) for c in same_bucket]
    open_minutes = []
    for c in same_bucket:
        if c.get("resolved_at"):
            try:
                start = datetime.fromisoformat(c["created_at"])
                end = datetime.fromisoformat(c["resolved_at"])
                open_minutes.append(max(0.0, (end - start).total_seconds() / 60.0))
            except Exception:
                continue
    reason_tags = [c["category"] for c in same_bucket if c.get("category")]
    top_tags = sorted(set(reason_tags), key=reason_tags.count, reverse=True)[:3]

    def _pctl(values, p):
        if not values:
            return None
        if len(values) == 1:
            return float(values[0])
        return float(statistics.quantiles(values, n=100, method="inclusive")[p - 1])

    min_events = await _min_events()
    doc = {
        "resident_id": resident_id,
        "bucket": bucket,
        "n_events": len(same_bucket),
        "typical_press_count_p50": _pctl(press_counts, 50),
        "typical_press_count_p90": _pctl(press_counts, 90),
        "typical_open_minutes_p50": _pctl(open_minutes, 50) if open_minutes else None,
        "common_reason_tags": top_tags,
        "burst_user": len(same_bucket) >= min_events and (_pctl(press_counts, 50) or 0) >= 3,
        "last_updated": datetime.now().isoformat(),
    }
    await db.resident_button_patterns.update_one(
        {"resident_id": resident_id, "bucket": bucket}, {"$set": doc}, upsert=True,
    )


@router.get("/{resident_id}")
async def get_patterns(resident_id: str, user=Depends(require_admin)):
    """Admin/staff read of every bucket's current pattern for a resident."""
    items = await db.resident_button_patterns.find(
        {"resident_id": resident_id}, {"_id": 0},
    ).sort("bucket", 1).to_list(24)
    return items
