"""Read-only pendant/RF FLEET views for the Admin/Staff UI.

Its own router on the /rf prefix (the same pattern rf_bridge_health.py
already uses) so it never edits rf.py. It only READS db.rf_devices /
db.rf_events / db.residents / db.alerts - no RF decoding, no press
semantics, no ResidentEvent logic. That lane is Claude 2's.

The Staff Dashboard "Devices in service" card used to query the retired
/pendants scaffold and always showed 0/0. It now calls
GET /rf/fleet/summary here, which every authenticated role may read and
which deliberately omits RF engineering detail (RSSI, match threshold,
raw fingerprint). GET /rf/fleet/devices is the admin/owner drill-down and
carries the full existing truth.
"""
from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import APIRouter, Depends

from deps import db, get_current_user, require_admin

router = APIRouter(prefix="/rf", tags=["rf-fleet"])

STALE_SEEN_HOURS = 24


def _iso(v):
    return v if isinstance(v, str) or v is None else v.isoformat()


def _parse(v) -> Optional[datetime]:
    if not v:
        return None
    try:
        dt = datetime.fromisoformat(v) if isinstance(v, str) else v
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except Exception:
        return None


def _status(d: dict, now: datetime) -> str:
    """Role-safe rollup status. 'offline' = disabled or not seen in 24h;
    'low_battery' = the device's own low_battery flag; else 'active'."""
    if not d.get("enabled", True):
        return "offline"
    seen = _parse(d.get("last_seen_at"))
    if seen is None or (now - seen) > timedelta(hours=STALE_SEEN_HOURS):
        return "offline"
    if d.get("low_battery"):
        return "low_battery"
    return "active"


def _human_ago(seen: Optional[datetime], now: datetime) -> str:
    if seen is None:
        return "never"
    s = int((now - seen).total_seconds())
    if s < 3600:
        return f"{max(1, s // 60)}m ago"
    if s < 86400:
        return f"{s // 3600}h ago"
    return f"{s // 86400}d ago"


def _reason(d: dict, status: str, now: datetime) -> Optional[str]:
    """Plain-English 'why does this need attention', derived only from existing
    RFDevice truth - no invented health states. None when the device is fine."""
    if not d.get("resident_id"):
        return "Not assigned to a resident"
    if not d.get("enabled", True):
        return "Disabled in RF settings"
    seen = _parse(d.get("last_seen_at"))
    if seen is None:
        return "No signal ever received since pairing"
    if status == "offline":
        return f"No signal in over {STALE_SEEN_HOURS}h - last heard {_human_ago(seen, now)}"
    if status == "low_battery":
        return f"Battery low - last heard {_human_ago(seen, now)}"
    return None


async def _resident_names() -> dict:
    return {
        r["resident_id"]: r.get("name")
        for r in await db.residents.find({}, {"_id": 0, "resident_id": 1, "name": 1}).to_list(2000)
    }


@router.get("/fleet/summary")
async def fleet_summary(user=Depends(get_current_user)):
    """Any authenticated role. Counts + a minimal per-device list. No RSSI,
    match score, or raw fingerprint - a nurse doesn't need RF internals."""
    now = datetime.now(timezone.utc)
    devices = await db.rf_devices.find({}, {"_id": 0}).sort("created_at", -1).to_list(500)
    names = await _resident_names()
    out = []
    in_service = need_attention = 0
    for d in devices:
        st = _status(d, now)
        if st == "active":
            in_service += 1
        else:
            need_attention += 1
        out.append({
            "rf_device_id": d.get("rf_device_id"),
            "label": d.get("label"),
            "resident_id": d.get("resident_id"),
            "resident_name": names.get(d.get("resident_id")),
            "room": d.get("room"),
            "status": st,
            "last_seen_at": _iso(d.get("last_seen_at")),
            "low_battery": bool(d.get("low_battery")),
            "press_count": d.get("press_count", 0),
            "reason": _reason(d, st, now),
        })
    return {
        "total": len(devices), "in_service": in_service, "need_attention": need_attention,
        "devices": out,
    }


@router.get("/fleet/devices")
async def fleet_devices(user=Depends(require_admin)):
    """Admin/owner drill-down: the full existing RFDevice truth, plus
    resolved resident name, recent RF events, and any open alert for the
    device's resident. All reads."""
    now = datetime.now(timezone.utc)
    devices = await db.rf_devices.find({}, {"_id": 0}).sort("created_at", -1).to_list(500)
    names = await _resident_names()
    recent = await db.rf_events.find({}, {"_id": 0}).sort("received_at", -1).to_list(400)
    open_alerts = await db.alerts.find(
        {"status": {"$in": ["active", "acknowledged"]}}, {"_id": 0, "alert_id": 1, "resident_id": 1, "severity": 1, "status": 1},
    ).to_list(1000)
    alert_by_res = {a["resident_id"]: a for a in open_alerts if a.get("resident_id")}

    out = []
    for d in devices:
        fp = d.get("fingerprint") or {}
        freq_hz = fp.get("frequency_hz")
        dev_events = [
            {"at": _iso(e.get("received_at") or e.get("captured_at")),
             "rssi": (e.get("fingerprint") or {}).get("rssi"),
             "match_score": e.get("match_score"), "kiosk_id": e.get("kiosk_id"),
             "alert_id": e.get("alert_id")}
            for e in recent if e.get("matched_device_id") == d.get("rf_device_id")
        ][:5]
        out.append({
            **{k: d.get(k) for k in (
                "rf_device_id", "label", "resident_id", "room", "severity", "match_threshold",
                "enabled", "press_count", "low_battery", "last_rssi", "pairing_warning",
            )},
            "resident_name": names.get(d.get("resident_id")),
            "status": _status(d, now),
            "frequency_mhz": round(freq_hz / 1_000_000, 4) if isinstance(freq_hz, (int, float)) else None,
            "last_seen_at": _iso(d.get("last_seen_at")),
            "recent_events": dev_events,
            "linked_alert": alert_by_res.get(d.get("resident_id")),
        })
    return {"total": len(devices), "devices": out}
