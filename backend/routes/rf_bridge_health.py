"""Tracks which kiosk_id(s) an actual physical RF bridge daemon is alive
and polling for - split out of rf.py (already well over the 300-line cap
before this addition) rather than growing that file further.

Root cause this exists to fix (2026-09-06, real pendant pairing incident):
the pairing UI's kiosk dropdown (RFPairingTab.jsx) previously listed EVERY
kiosk in the system as an equally valid choice for "listen for a new
pendant", with no way to tell that only ONE physical SDR bridge exists in
this deployment (bound to a single kiosk_id) - every other kiosk has no
SDR attached at all. Picking a resident's own room kiosk (the natural,
wrong assumption) meant the capture window silently never had anything
listening for it - it timed out no matter what was pressed, for reasons
that had nothing to do with the pendant itself.
"""
from datetime import timedelta

from fastapi import APIRouter, Depends

from deps import db, require_admin
from models import now_utc

router = APIRouter(prefix="/rf", tags=["rf"])

# A bridge daemon polls /bridge/{kiosk_id}/pending roughly once per second
# (see android-bridge/caos_rf_bridge.py) - anything quieter than this for
# more than a few seconds means no real bridge is currently alive for that
# kiosk_id, not just a slow poll cycle.
BRIDGE_ALIVE_WINDOW_SECONDS = 10


async def mark_bridge_polled(kiosk_id: str) -> None:
    """Called on every real bridge poll - cheap, fire-and-forget liveness signal."""
    await db.kiosks.update_one(
        {"kiosk_id": kiosk_id}, {"$set": {"last_bridge_poll_at": now_utc().isoformat()}},
    )


async def list_active_bridge_kiosk_ids() -> list[str]:
    """Kiosk ids with a real bridge daemon alive right now, per the above
    window - the only kiosks a "listen for a new pendant" capture can ever
    actually succeed against."""
    cutoff = (now_utc() - timedelta(seconds=BRIDGE_ALIVE_WINDOW_SECONDS)).isoformat()
    docs = await db.kiosks.find(
        {"last_bridge_poll_at": {"$gte": cutoff}}, {"_id": 0, "kiosk_id": 1},
    ).to_list(50)
    return [d["kiosk_id"] for d in docs]


@router.get("/bridges/active")
async def active_bridges(user=Depends(require_admin)):
    """Kiosk ids with a real SDR bridge daemon polling right now - the only
    ones a pairing capture can ever succeed against. Lets the pairing UI
    stop offering every kiosk as an equally valid target when only one
    physical bridge exists in this deployment."""
    return {"kiosk_ids": await list_active_bridge_kiosk_ids()}
