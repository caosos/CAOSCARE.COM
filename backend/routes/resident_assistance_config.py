"""Per-facility config for the Level 1 resident-assistance event model
(2026-09-06 directive). Same shape as routes/escalation.py's rule
CRUD - keyed by facility_id, GET never 404s (falls back to defaults so the
UI always has something to render), PUT upserts.
"""
from fastapi import APIRouter, Depends

from deps import db, require_admin
from models import ResidentAssistanceConfig, now_utc

router = APIRouter(prefix="/resident-assistance-config", tags=["resident-assistance-config"])


def _iso(doc: dict) -> dict:
    v = doc.get("updated_at")
    if v and not isinstance(v, str):
        doc["updated_at"] = v.isoformat()
    return doc


async def get_effective_config(facility_id: str | None) -> dict:
    """Plain importable lookup (not the HTTP route, which is admin-gated) -
    used by routes/realtime.py to hand the resident-facing session its
    community-configured timeouts without exposing a public config
    endpoint. Same never-404, fall-back-to-defaults shape as the route."""
    cfg = await db.resident_assistance_config.find_one({"facility_id": facility_id}, {"_id": 0})
    return cfg or ResidentAssistanceConfig(facility_id=facility_id).model_dump()


@router.get("")
async def get_config(facility_id: str | None = None, user=Depends(require_admin)):
    return _iso(await get_effective_config(facility_id))


@router.put("")
async def upsert_config(cfg: ResidentAssistanceConfig, user=Depends(require_admin)):
    cfg.updated_at = now_utc()
    doc = cfg.model_dump()
    doc["updated_at"] = doc["updated_at"].isoformat()
    await db.resident_assistance_config.update_one(
        {"facility_id": cfg.facility_id}, {"$set": doc}, upsert=True,
    )
    return doc
