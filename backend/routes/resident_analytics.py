"""Resident movement/stats/briefing — read-only clinical intelligence over
the same resident/alert/location/memory records. Split out of residents.py
(CRUD + identity) to keep that file focused and under the line-count cap;
this is a distinct responsibility (aggregation/reporting), not a chop."""
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, HTTPException, Depends
from deps import db, get_current_user

router = APIRouter(prefix="/residents", tags=["residents"])


@router.get("/{resident_id}/movement")
async def resident_movement(resident_id: str, hours: int = 24, user=Depends(get_current_user)):
    """Zone-visit timeline for a resident over the last N hours."""
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    locs = await db.locations.find(
        {"resident_id": resident_id, "created_at": {"$gte": cutoff}},
        {"_id": 0},
    ).sort("created_at", 1).to_list(5000)
    # Collapse consecutive pings in the same zone into a "visit"
    visits = []
    for l in locs:
        if visits and visits[-1]["zone"] == l["zone"]:
            visits[-1]["until"] = l["created_at"]
            visits[-1]["pings"] += 1
        else:
            visits.append({
                "zone": l["zone"],
                "from": l["created_at"],
                "until": l["created_at"],
                "pings": 1,
                "source": l.get("source"),
            })
    return {"visits": visits, "total_pings": len(locs)}


@router.get("/{resident_id}/stats")
async def resident_stats(resident_id: str, days: int = 30, user=Depends(get_current_user)):
    """Clinician-facing aggregate for a resident over the last N days.

    Breaks calls down by category so a nurse can see at a glance:
    "Maggie — 14 bathroom assists this week (up from 8), 2 falls in 30 days,
    avg response 4m 12s."
    """
    resident = await db.residents.find_one({"resident_id": resident_id}, {"_id": 0})
    if not resident:
        raise HTTPException(status_code=404, detail="Resident not found")

    now_dt = datetime.now(timezone.utc)
    cutoff = (now_dt - timedelta(days=days)).isoformat()
    prev_cutoff = (now_dt - timedelta(days=days * 2)).isoformat()

    curr = await db.alerts.find(
        {"resident_id": resident_id, "created_at": {"$gte": cutoff}},
        {"_id": 0},
    ).to_list(2000)
    prev = await db.alerts.find(
        {"resident_id": resident_id, "created_at": {"$gte": prev_cutoff, "$lt": cutoff}},
        {"_id": 0},
    ).to_list(2000)

    def _bucket(items):
        out = {
            "total_calls": len(items),
            "by_category": {},
            "by_severity": {},
            "avg_response_s": None,
            "max_response_s": None,
            "avg_duration_s": None,
            "falls_during_call": 0,
            "unresolved": 0,
        }
        response_times = [a["response_seconds"] for a in items if isinstance(a.get("response_seconds"), int)]
        durations = [a["duration_seconds"] for a in items if isinstance(a.get("duration_seconds"), int)]
        for a in items:
            c = a.get("category") or "unclassified"
            out["by_category"][c] = out["by_category"].get(c, 0) + 1
            s = a.get("severity") or "assist"
            out["by_severity"][s] = out["by_severity"].get(s, 0) + 1
            if a.get("category") == "fall":
                out["falls_during_call"] += 1
            if a.get("status") != "resolved":
                out["unresolved"] += 1
        if response_times:
            out["avg_response_s"] = int(sum(response_times) / len(response_times))
            out["max_response_s"] = max(response_times)
        if durations:
            out["avg_duration_s"] = int(sum(durations) / len(durations))
        return out

    current = _bucket(curr)
    previous = _bucket(prev)

    # Last 10 events, lightweight shape
    recent = sorted(curr, key=lambda a: a.get("created_at", ""), reverse=True)[:10]
    recent_events = [{
        "alert_id": a["alert_id"],
        "created_at": a.get("created_at"),
        "category": a.get("category") or "unclassified",
        "severity": a.get("severity"),
        "status": a.get("status"),
        "response_seconds": a.get("response_seconds"),
        "duration_seconds": a.get("duration_seconds"),
        "ai_summary": a.get("ai_summary"),
        "resident_stated_reason": a.get("resident_stated_reason"),
        "outcome": a.get("outcome"),
    } for a in recent]

    return {
        "resident": {"resident_id": resident_id, "name": resident["name"], "room": resident["room"]},
        "window_days": days,
        "current_window": current,
        "previous_window": previous,
        "recent_events": recent_events,
    }


@router.get("/{resident_id}/briefing")
async def resident_briefing(resident_id: str, user=Depends(get_current_user)):
    """Concise clinical + situational briefing — structured JSON plus a
    pre-composed natural-language line ready for TTS. Built for nurse
    accessibility: a shift-change reader, a sighted-overview for the
    caregiver entering the room, or a voice read-back on the kiosk."""
    resident = await db.residents.find_one({"resident_id": resident_id}, {"_id": 0})
    if not resident:
        raise HTTPException(status_code=404, detail="Resident not found")

    # Active/unresolved alerts in the last 24h
    cutoff_24h = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
    active_alerts = await db.alerts.count_documents({
        "resident_id": resident_id,
        "status": {"$in": ["active", "acknowledged"]},
        "created_at": {"$gte": cutoff_24h},
    })

    # Top pinned memories (nurse's cheat-sheet)
    pinned = await db.memories.find(
        {"resident_id": resident_id, "pinned": True},
        {"_id": 0, "text": 1, "category": 1, "importance": 1},
    ).sort([("importance", -1)]).to_list(5)

    # Last known zone
    last_loc = await db.locations.find_one(
        {"resident_id": resident_id}, {"_id": 0},
        sort=[("created_at", -1)],
    )
    last_zone = last_loc.get("zone") if last_loc else None

    thresholds = resident.get("clinical_thresholds") or {}
    preferred = resident.get("preferred_name") or resident["name"].split(" ")[0]

    # --- Compose the spoken narrative ---
    parts = [f"Briefing for {resident['name']}, room {resident['room']}."]
    if resident.get("preferred_name") and resident["preferred_name"] != preferred:
        parts.append(f"Goes by {resident['preferred_name']}.")
    elif resident.get("preferred_name"):
        parts.append(f"Goes by {resident['preferred_name']}.")

    # Clinical thresholds, spoken plain-English
    def _t(k):
        v = thresholds.get(k)
        return v if (isinstance(v, (int, float)) and v) else None

    hr_min, hr_max, hr_ex = _t("hr_resting_min"), _t("hr_resting_max"), _t("hr_exertion_max")
    spo2 = _t("spo2_min")
    if hr_min or hr_max or hr_ex or spo2:
        bits = []
        if hr_min and hr_max:
            bits.append(f"resting heart rate band {hr_min} to {hr_max}")
        elif hr_max:
            bits.append(f"resting heart rate up to {hr_max}")
        if hr_ex:
            bits.append(f"exertion ceiling {hr_ex}")
        if spo2:
            bits.append(f"oxygen floor {spo2} percent")
        parts.append("Clinical bands: " + ", ".join(bits) + ".")
        if thresholds.get("notes"):
            parts.append(f"Note: {thresholds['notes']}.")
    else:
        parts.append("No custom clinical bands set.")

    # Active alerts
    if active_alerts > 0:
        parts.append(
            f"{active_alerts} unresolved alert{'s' if active_alerts > 1 else ''} in the last 24 hours."
        )
    else:
        parts.append("No open alerts.")

    # Location
    if last_zone:
        parts.append(f"Last seen in {last_zone}.")

    # Pinned cheat-sheet memories — keep it short, drop very similar ones
    if pinned:
        spoken_mem = "; ".join(p["text"].rstrip(".").strip() for p in pinned[:3])
        parts.append(f"Key things to know: {spoken_mem}.")

    narrative = " ".join(parts)

    return {
        "resident": {
            "resident_id": resident["resident_id"],
            "name": resident["name"],
            "preferred_name": resident.get("preferred_name") or "",
            "room": resident["room"],
            "participation_level": resident.get("participation_level"),
        },
        "clinical_thresholds": resident.get("clinical_thresholds") or None,
        "active_alerts_24h": active_alerts,
        "pinned_memories": pinned,
        "last_zone": last_zone,
        "last_seen_at": last_loc.get("created_at") if last_loc else None,
        "narrative": narrative,
    }
