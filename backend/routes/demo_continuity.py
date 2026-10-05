"""RQ-001 demo data continuity control surface. Owner/admin only.

GET  /api/demo/continuity           the continuity record (last_simulated_at,
                                    receipt chain ids, windows processed)
POST /api/demo/continuity/catch-up  process every whole window since then

Catch-up also runs on backend startup and after a staff sign-in when
CAOSCARE_DEMO_CONTINUITY_AUTO is set (default off); this endpoint is for an
operator who wants it now. Each window is processed once, receipted, and
touches only simulated demo-room work.
"""
from fastapi import APIRouter, Depends

from deps import require_admin
import demo_continuity as continuity

router = APIRouter(prefix="/demo/continuity", tags=["demo"])


@router.get("")
async def continuity_state(user=Depends(require_admin)):
    return {"state": await continuity.get_state(), "window_hours": continuity.WINDOW.total_seconds() / 3600,
            "max_windows": continuity.MAX_WINDOWS, "open_cap": continuity.OPEN_CAP,
            "auto_enabled": continuity.auto_enabled()}


@router.post("/catch-up")
async def continuity_catch_up(user=Depends(require_admin)):
    return await continuity.catch_up(trigger=f"operator:{user.get('user_id')}")
