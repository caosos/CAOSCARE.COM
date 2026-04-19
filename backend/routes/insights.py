"""Insights / pattern detection - Phase 4 seed.

Computes per-resident behavioral deltas:
  - help_requests_7d vs prior 7d (alert creation count)
  - nighttime_activity_7d vs prior 7d (alerts 22:00-06:00)
  - mobility_7d vs prior 7d (distinct zones visited per day avg)
  - response_burden_7d (total alert count regardless of baseline)

Classifies each into {info, watch, concern} with a confidence score.
Runs on-demand via POST /api/insights/compute (no background scheduler needed in MVP).
"""
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends
from models import Insight, now_utc
from deps import db, get_current_user

router = APIRouter(prefix="/insights", tags=["insights"])


def _severity_and_confidence(deviation_pct: float, sample_size: int):
    """Simple heuristic:
       - confidence = min(1.0, sample_size / 10)
       - severity:  |dev| >= 100% -> concern, >= 50% -> watch, else info
    """
    confidence = round(min(1.0, max(sample_size, 0) / 10.0), 2)
    abs_dev = abs(deviation_pct)
    if abs_dev >= 1.0:
        sev = "concern"
    elif abs_dev >= 0.5:
        sev = "watch"
    else:
        sev = "info"
    return sev, confidence


async def _count_alerts(resident_id: str, since_iso: str, until_iso: str, night_only: bool = False) -> int:
    q = {
        "resident_id": resident_id,
        "created_at": {"$gte": since_iso, "$lt": until_iso},
    }
    if not night_only:
        return await db.alerts.count_documents(q)
    # Night: hour >= 22 or < 6. Pull and filter locally (MongoDB string date comparison limitation).
    docs = await db.alerts.find(q, {"_id": 0, "created_at": 1}).to_list(2000)
    n = 0
    for d in docs:
        try:
            dt = datetime.fromisoformat(d["created_at"])
            if dt.hour >= 22 or dt.hour < 6:
                n += 1
        except Exception:
            continue
    return n


async def _mobility(resident_id: str, since_iso: str, until_iso: str) -> int:
    """Distinct zones visited in the window."""
    zones = await db.locations.distinct("zone", {
        "resident_id": resident_id,
        "created_at": {"$gte": since_iso, "$lt": until_iso},
    })
    return len([z for z in zones if z])


async def compute_for_resident(resident: dict):
    """Returns list of Insight dicts for the given resident (already serialized)."""
    now_dt = datetime.now(timezone.utc)
    cur_start = now_dt - timedelta(days=7)
    base_start = now_dt - timedelta(days=14)

    cur_from = cur_start.isoformat()
    cur_to = now_dt.isoformat()
    base_from = base_start.isoformat()
    base_to = cur_from

    rid = resident["resident_id"]
    name = resident.get("preferred_name") or resident.get("name")

    out = []

    # 1. Help requests
    cur_help = await _count_alerts(rid, cur_from, cur_to)
    base_help = await _count_alerts(rid, base_from, base_to)
    if cur_help > 0 or base_help > 0:
        denom = base_help if base_help > 0 else 1
        dev = (cur_help - denom) / denom
        sev, conf = _severity_and_confidence(dev, cur_help + base_help)
        if cur_help > base_help:
            title = f"Help requests trending up for {name}"
        elif cur_help < base_help:
            title = f"Help requests down for {name}"
        else:
            title = f"Help requests steady for {name}"
        desc = f"Last 7 days: {cur_help} request{'s' if cur_help != 1 else ''}. Prior 7 days: {base_help}."
        out.append({
            "resident_id": rid,
            "resident_name": name,
            "metric": "help_requests_7d",
            "current_value": float(cur_help),
            "baseline_value": float(base_help),
            "deviation_pct": round(dev, 2),
            "severity": sev,
            "confidence": conf,
            "title": title,
            "description": desc,
        })

    # 2. Nighttime activity
    cur_night = await _count_alerts(rid, cur_from, cur_to, night_only=True)
    base_night = await _count_alerts(rid, base_from, base_to, night_only=True)
    if cur_night > 0 or base_night > 0:
        denom = base_night if base_night > 0 else 1
        dev = (cur_night - denom) / denom
        sev, conf = _severity_and_confidence(dev, cur_night + base_night)
        title = (
            f"Nighttime activity up for {name}" if cur_night > base_night
            else f"Nighttime activity steady for {name}"
        )
        desc = f"Last 7 nights: {cur_night} alert{'s' if cur_night != 1 else ''} between 10 PM – 6 AM. Prior 7: {base_night}."
        out.append({
            "resident_id": rid,
            "resident_name": name,
            "metric": "nighttime_activity_7d",
            "current_value": float(cur_night),
            "baseline_value": float(base_night),
            "deviation_pct": round(dev, 2),
            "severity": sev,
            "confidence": conf,
            "title": title,
            "description": desc,
        })

    # 3. Mobility
    cur_mob = await _mobility(rid, cur_from, cur_to)
    base_mob = await _mobility(rid, base_from, base_to)
    if cur_mob > 0 or base_mob > 0:
        denom = base_mob if base_mob > 0 else 1
        dev = (cur_mob - denom) / denom
        sev, conf = _severity_and_confidence(dev, cur_mob + base_mob)
        if cur_mob < base_mob:
            title = f"Mobility decreased for {name}"
            sev = "watch" if sev == "info" else sev
        elif cur_mob > base_mob:
            title = f"Mobility up for {name}"
        else:
            title = f"Mobility steady for {name}"
        desc = f"Last 7 days: {cur_mob} distinct zone{'s' if cur_mob != 1 else ''} visited. Prior 7: {base_mob}."
        out.append({
            "resident_id": rid,
            "resident_name": name,
            "metric": "mobility_7d",
            "current_value": float(cur_mob),
            "baseline_value": float(base_mob),
            "deviation_pct": round(dev, 2),
            "severity": sev,
            "confidence": conf,
            "title": title,
            "description": desc,
        })

    return out


@router.post("/compute")
async def compute_all(user=Depends(get_current_user)):
    """Wipes old insights and recomputes for every resident. Returns count."""
    await db.insights.delete_many({})
    residents = await db.residents.find({}, {"_id": 0}).to_list(1000)
    count = 0
    for r in residents:
        items = await compute_for_resident(r)
        for it in items:
            ins = Insight(**it)
            doc = ins.model_dump()
            doc["created_at"] = doc["created_at"].isoformat()
            await db.insights.insert_one(doc)
            count += 1
    return {"computed": count, "residents": len(residents)}


@router.get("")
async def list_insights(user=Depends(get_current_user)):
    """All current insights, sorted by severity (concern first) then confidence."""
    items = await db.insights.find({}, {"_id": 0}).to_list(500)
    sev_rank = {"concern": 0, "watch": 1, "info": 2}
    items.sort(key=lambda x: (sev_rank.get(x.get("severity", "info"), 99), -x.get("confidence", 0)))
    for it in items:
        ca = it.get("created_at")
        if ca and not isinstance(ca, str):
            it["created_at"] = ca.isoformat()
    return items


@router.get("/resident/{resident_id}")
async def insights_for_resident(resident_id: str, user=Depends(get_current_user)):
    items = await db.insights.find({"resident_id": resident_id}, {"_id": 0}).to_list(100)
    for it in items:
        ca = it.get("created_at")
        if ca and not isinstance(ca, str):
            it["created_at"] = ca.isoformat()
    return items


@router.get("/summary")
async def summary(user=Depends(get_current_user)):
    """Counts per severity for the staff dashboard badge."""
    concern = await db.insights.count_documents({"severity": "concern"})
    watch = await db.insights.count_documents({"severity": "watch"})
    info = await db.insights.count_documents({"severity": "info"})
    return {"concern": concern, "watch": watch, "info": info, "total": concern + watch + info}
