"""Family portal - magic-link access for family contacts.

Each FamilyContact has a `portal_token` that acts like a long-lived, resident-scoped
auth token. Family members visit `/family/{portal_token}` in the browser; the portal
calls `GET /api/family-portal/{portal_token}/summary` to fetch a curated, privacy-
respectful view of their loved one: name, room, participation level, last-seen zone,
recent alerts (summarized, no medical detail), and the bedtime "Daily Haiku" digest
when generated.
"""
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, HTTPException
from deps import db

router = APIRouter(prefix="/family-portal", tags=["family-portal"])


def _iso(v):
    if v is None or isinstance(v, str):
        return v
    return v.isoformat()


async def _contact_by_token(token: str) -> dict:
    contact = await db.family_contacts.find_one({"portal_token": token}, {"_id": 0})
    if not contact:
        raise HTTPException(status_code=404, detail="Invalid or expired family link")
    return contact


@router.get("/{token}/summary")
async def portal_summary(token: str):
    contact = await _contact_by_token(token)
    resident = await db.residents.find_one({"resident_id": contact["resident_id"]}, {"_id": 0})
    if not resident:
        raise HTTPException(status_code=404, detail="Resident not found")

    # Last-seen location
    last_loc = await db.locations.find_one(
        {"resident_id": resident["resident_id"]},
        {"_id": 0},
        sort=[("created_at", -1)],
    )
    last_seen = {
        "zone": last_loc.get("zone") if last_loc else None,
        "at": _iso(last_loc.get("created_at")) if last_loc else None,
    }

    # Recent alerts (summarized - no medical detail, no chat content)
    cutoff = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
    alerts = await db.alerts.find(
        {"resident_id": resident["resident_id"], "created_at": {"$gte": cutoff}},
        {"_id": 0, "alert_id": 1, "severity": 1, "status": 1, "triggered_by": 1, "created_at": 1, "resolved_at": 1, "outcome": 1},
    ).sort("created_at", -1).to_list(20)
    for a in alerts:
        a["created_at"] = _iso(a.get("created_at"))
        a["resolved_at"] = _iso(a.get("resolved_at"))

    # Stats
    active_count = await db.alerts.count_documents({
        "resident_id": resident["resident_id"],
        "status": {"$in": ["active", "acknowledged"]},
    })
    resolved_7d = await db.alerts.count_documents({
        "resident_id": resident["resident_id"],
        "status": "resolved",
        "resolved_at": {"$gte": cutoff},
    })

    # Recent haiku digest (if any)
    haiku = await db.haikus.find_one(
        {"resident_id": resident["resident_id"]},
        {"_id": 0},
        sort=[("created_at", -1)],
    )
    if haiku:
        haiku["created_at"] = _iso(haiku.get("created_at"))

    return {
        "resident": {
            "name": resident.get("preferred_name") or resident.get("name"),
            "room": resident.get("room"),
            "participation_level": resident.get("participation_level"),
        },
        "contact": {
            "name": contact["name"],
            "relationship": contact.get("relationship"),
            "notify_on": contact.get("notify_on", []),
        },
        "last_seen": last_seen,
        "active_now": active_count,
        "resolved_last_7d": resolved_7d,
        "recent_alerts": alerts,
        "haiku": haiku,
    }


@router.post("/{token}/acknowledge-read")
async def acknowledge_read(token: str):
    """Family taps 'I've seen this' — just logs it for transparency."""
    contact = await _contact_by_token(token)
    await db.family_portal_reads.insert_one({
        "contact_id": contact["contact_id"],
        "resident_id": contact["resident_id"],
        "at": datetime.now(timezone.utc).isoformat(),
    })
    return {"ok": True}
