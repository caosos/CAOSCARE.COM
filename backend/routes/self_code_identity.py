"""Who may inspect Aria's own source: the verified Room 214 session only.

Owner feature (Michael, 2026-10-15): the Aria instance serving ROOM 214 may
read the CAOSCARE source relevant to herself. Nobody else - no other resident
room, no demo/simulated room, not the owner /aria build, not Admin Aria, not
the telephone build, no API caller.

The gate never trusts a caller-supplied room, resident_id, kiosk_id or tool
argument. It proves the identity from what the backend itself wrote and
holds:

  1. the canonical Room 214 kiosk record (db.kiosks: room "214", not the
     public demo kiosk) and the resident that kiosk speaks for
     (routes.kiosk_identity.resident_for_kiosk - pinned resident first);
  2. the live room lease the backend created at session mint
     (db.resident_aria_leases, written by claim_or_reuse_room_lease, never by
     a client) - it must be the lease for THIS session_id, live and fresh,
     and its room / kiosk / resident must all equal the canonical record;
  3. the request must arrive through the Room 214 node's own page proxy
     (room-node/aria_wake/serve_built.js on the same host -> loopback). A
     direct LAN caller is refused even with a matching lease.

Anything that cannot be positively proven is refused (fail closed). Every
refusal carries a reason code so the receipt says why.

Kill switch: CAOSCARE_SELF_INSPECT=off disables the capability everywhere
without a code change.
"""
import os
from datetime import timedelta
from typing import Optional

from fastapi import Request

from deps import db
from models import now_utc
from routes.kiosk_identity import resident_for_kiosk
from routes.realtime_room_lease import STALE_SECONDS

SELF_INSPECT_ROOM = "214"
_LIVE = ("activating", "active")


def enabled() -> bool:
    return (os.environ.get("CAOSCARE_SELF_INSPECT", "on") or "on").strip().lower() not in ("off", "0", "false", "no")


def allowed_origins() -> set:
    """Client addresses the Room 214 page proxy can arrive from. The built
    Room page (serve_built.js) binds 127.0.0.1 and proxies /api to the backend
    on the same host, so the backend sees loopback."""
    raw = os.environ.get("CAOSCARE_SELF_INSPECT_ORIGINS", "127.0.0.1,::1")
    return {o.strip() for o in raw.split(",") if o.strip()}


def _refused(reason: str, **facts) -> dict:
    return {"allowed": False, "reason": reason, "room": SELF_INSPECT_ROOM, **facts}


async def canonical_room() -> Optional[dict]:
    """The one kiosk + resident record Room 214 Aria speaks for, from the
    server's own records. None when it cannot be established unambiguously."""
    kiosks = await db.kiosks.find(
        {"room": SELF_INSPECT_ROOM, "public_demo": {"$ne": True}}, {"_id": 0},
    ).to_list(5)
    if len(kiosks) != 1:
        return None
    kiosk = kiosks[0]
    resident = await resident_for_kiosk(kiosk, {"resident_id": 1, "synthetic": 1, "preferred_name": 1})
    if not resident or resident.get("synthetic"):
        return None
    return {"kiosk_id": kiosk["kiosk_id"], "resident_id": resident["resident_id"]}


async def _live_lease(session_id: str) -> Optional[dict]:
    cutoff = (now_utc() - timedelta(seconds=STALE_SECONDS)).isoformat()
    return await db.resident_aria_leases.find_one({
        "session_id": session_id, "status": {"$in": list(_LIVE)},
        "last_seen_at": {"$gte": cutoff},
    }, {"_id": 0})


def _matches_canonical(lease: dict, canonical: dict, claimed_resident: Optional[str]) -> Optional[str]:
    """Reason the lease is not the canonical Room 214 session, or None."""
    if lease.get("room") != SELF_INSPECT_ROOM:
        return "not_room_214"
    if lease.get("kiosk_id") != canonical["kiosk_id"]:
        return "kiosk_mismatch"
    if lease.get("resident_id") != canonical["resident_id"]:
        return "resident_mismatch"
    if claimed_resident and claimed_resident != lease.get("resident_id"):
        return "resident_claim_mismatch"
    return None


async def verify_room214_session(session_id: Optional[str], resident_id: Optional[str],
                                 request: Optional[Request]) -> dict:
    """Full call-time gate. Returns {"allowed": True, ...identity} or
    {"allowed": False, "reason": ...}. `request` None = no origin to check =
    refused (an HTTP tool call always has one; only tests pass None)."""
    if not enabled():
        return _refused("disabled")
    if not session_id or not resident_id:
        return _refused("missing_session")
    canonical = await canonical_room()
    if not canonical:
        return _refused("no_canonical_room_record")
    lease = await _live_lease(session_id)
    if not lease:
        return _refused("no_live_session", session_id=session_id)
    why = _matches_canonical(lease, canonical, resident_id)
    if why:
        return _refused(why, session_id=session_id, lease_room=lease.get("room"))
    origin = request.client.host if (request and request.client) else None
    if origin not in allowed_origins():
        return _refused("origin_not_room_node", session_id=session_id, origin=origin)
    return {
        "allowed": True, "room": SELF_INSPECT_ROOM, "session_id": session_id,
        "resident_id": lease["resident_id"], "kiosk_id": lease["kiosk_id"],
        "trigger_source": lease.get("trigger_source"), "origin": origin,
        "authority": "room214_lease_verified",
    }


async def is_room214_mint(payload: dict, lease: Optional[dict]) -> bool:
    """Mint-time decision: does the session being created belong to the
    canonical Room 214 record? Used only to decide whether the tools are
    declared to the model. The call-time gate above re-proves everything
    (including origin) on every use, so declaring is never granting."""
    if not enabled() or not lease or not lease.get("claimed"):
        return False
    canonical = await canonical_room()
    if not canonical:
        return False
    claim = {"room": payload.get("room"), "kiosk_id": payload.get("kiosk_id"),
             "resident_id": payload.get("resident_id")}
    return _matches_canonical(claim, canonical, None) is None
