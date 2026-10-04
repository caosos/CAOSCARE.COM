"""Which authority a resident room claim may carry on its receipts."""
from typing import Optional

from fastapi import HTTPException

from deps import db


async def room_claim_authority(room: Optional[str], origin_authority: Optional[str]) -> str:
    """The authority a room claim may carry (never staff action - a room claim
    can only create or re-ask, see task_lifecycle.authority_for):
    - "public_resident_bus": the unauthenticated room surface (browser screen
      or realtime voice); origin receipt labelled unverified.
    - "registered_endpoint:<kiosk_id>": an authenticated bridge caller
      (voice_bridge.py) for a registered endpoint of this same room. Only
      in-process callers can pass it; the HTTP route never does."""
    if not origin_authority:
        return "public_resident_bus"
    prefix = "registered_endpoint:"
    if origin_authority.startswith(prefix):
        kiosk = await db.kiosks.find_one({"kiosk_id": origin_authority[len(prefix):]}, {"_id": 0, "room": 1})
        if kiosk and kiosk.get("room") and kiosk["room"] == room:
            return origin_authority
    raise HTTPException(status_code=403, detail="Request origin is not an allowed authority")
