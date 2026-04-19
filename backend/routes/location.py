"""Indoor location tracking - mock generator + real sensor ingest + latest lookups."""
import random
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, HTTPException
from models import LocationUpdate, LocationUpdateCreate, now_utc
from deps import db, get_current_user

router = APIRouter(prefix="/locations", tags=["locations"])


def _iso(doc: dict) -> dict:
    ca = doc.get("created_at")
    if ca and not isinstance(ca, str):
        doc["created_at"] = ca.isoformat()
    return doc


@router.post("")
async def ingest_location(data: LocationUpdateCreate):
    """Real sensors / mesh network POST here. Public so field hardware can report directly."""
    exists = await db.residents.find_one({"resident_id": data.resident_id}, {"_id": 0})
    if not exists:
        raise HTTPException(status_code=404, detail="Resident not found")
    upd = LocationUpdate(**data.model_dump())
    doc = upd.model_dump()
    doc["created_at"] = doc["created_at"].isoformat()
    await db.locations.insert_one(doc)
    doc.pop("_id", None)
    return doc


@router.get("/latest")
async def latest_locations(user=Depends(get_current_user)):
    """Latest location per resident, enriched with resident name."""
    residents = await db.residents.find({}, {"_id": 0}).to_list(1000)
    out = []
    for r in residents:
        latest = await db.locations.find_one(
            {"resident_id": r["resident_id"]},
            {"_id": 0},
            sort=[("created_at", -1)],
        )
        if latest:
            _iso(latest)
            out.append({
                "resident_id": r["resident_id"],
                "resident_name": r["name"],
                "room": r.get("room"),
                "zone": latest.get("zone"),
                "last_seen": latest.get("created_at"),
                "source": latest.get("source"),
                "signal_strength": latest.get("signal_strength"),
            })
        else:
            out.append({
                "resident_id": r["resident_id"],
                "resident_name": r["name"],
                "room": r.get("room"),
                "zone": None,
                "last_seen": None,
                "source": None,
                "signal_strength": None,
            })
    return out


@router.get("/resident/{resident_id}")
async def resident_history(resident_id: str, limit: int = 50, user=Depends(get_current_user)):
    items = (
        await db.locations.find({"resident_id": resident_id}, {"_id": 0})
        .sort("created_at", -1)
        .to_list(limit)
    )
    return [_iso(i) for i in items]


DEFAULT_ZONES = [
    "Room", "Hallway A", "Hallway B", "Dining Room", "Lounge",
    "Garden Patio", "Chapel", "Activity Room", "Nurse Station",
]


@router.post("/mock/generate")
async def generate_mock_location(user=Depends(get_current_user)):
    """Generate a random location update for every resident (simulates mesh network ping)."""
    residents = await db.residents.find({}, {"_id": 0}).to_list(1000)
    if not residents:
        return {"generated": 0}
    created = []
    for r in residents:
        zone = random.choice(DEFAULT_ZONES)
        upd = LocationUpdate(
            resident_id=r["resident_id"],
            zone=zone,
            room=r.get("room"),
            signal_strength=random.randint(60, 100),
            source="mock",
        )
        doc = upd.model_dump()
        doc["created_at"] = doc["created_at"].isoformat()
        await db.locations.insert_one(doc)
        doc.pop("_id", None)
        created.append(doc)
    return {"generated": len(created), "updates": created}
