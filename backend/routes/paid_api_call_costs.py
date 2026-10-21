"""Read-only, admin-scoped per-call estimates from the existing paid API ledger.

This is a projection of ``paid_api_ledger`` receipts, not a second ledger.  It
never returns provider identifiers, usage payloads, credentials, or call text.
Missing usage remains unknown; it is never converted to a zero-dollar call.
"""
import asyncio
from collections import defaultdict

from fastapi import APIRouter, Depends

from deps import db, require_admin
from routes.paid_api_receipts import ledger


router = APIRouter(prefix="/paid-api/call-costs", tags=["paid-api-costs"])
_USAGE_KINDS = {"provider_usage", "provider_request"}


def _environment(provenance):
    p = provenance or {}
    purpose = str(p.get("run_purpose") or "").lower()
    database = str(p.get("db_name") or "").lower()
    if database == "caoscare" and purpose in (None, "", "unknown", "live"):
        return "live"
    if any(mark in purpose for mark in ("test", "gate", "scratch", "sim")) or \
            any(mark in database for mark in ("test", "gate", "scratch", "sim")):
        return "development_test"
    return "unknown"


def summarize_latest_calls(rooms, mint_receipts, related_receipts):
    """Return one latest call summary for every requested room.

    A mint is the durable start of a call attempt, so failed and zero-turn
    attempts are included.  Only counted billable usage receipts contribute to
    the estimate.  Any missing/incomplete usage makes the total incomplete.
    """
    keys = [str(room) for room in rooms if room not in (None, "")]
    latest = {}
    for receipt in sorted(mint_receipts, key=lambda x: x.get("recorded_at") or "", reverse=True):
        room = str(((receipt.get("provenance") or {}).get("room")) or "")
        session_id = receipt.get("session_id")
        if room in keys and session_id and room not in latest:
            latest[room] = receipt

    by_session = defaultdict(list)
    by_secret = defaultdict(list)
    for receipt in related_receipts:
        if receipt.get("session_id"):
            by_session[receipt["session_id"]].append(receipt)
        if receipt.get("session_secret_fp"):
            by_secret[receipt["session_secret_fp"]].append(receipt)

    out = {}
    for room in keys:
        mint = latest.get(room)
        if not mint:
            out[room] = {"room": room, "call_status": "no_call", "estimate_status": "unavailable",
                         "estimated_usd": None, "known_estimated_usd": None,
                         "environment": None, "recorded_at": None, "usage_receipts": 0}
            continue
        session_id = mint["session_id"]
        docs = list(by_session.get(session_id, []))
        docs += by_secret.get(mint.get("session_secret_fp"), []) if mint.get("session_secret_fp") else []
        ended = max((d for d in docs if d.get("kind") == "session_ended"),
                    key=lambda x: x.get("recorded_at") or "", default=None)
        connected = any(d.get("kind") == "session_connected" and d.get("billable_activity") is True for d in docs)
        # A counted usage receipt with missing provider usage is still evidence
        # for this call.  Keep it in the total so a partly reported call stays
        # incomplete instead of looking like a complete, cheaper call.
        usage = [d for d in docs if d.get("kind") in _USAGE_KINDS
                 and d.get("billable_activity") is not False and d.get("counted") is not False]
        values = [((d.get("estimate") or {}).get("usd")) for d in usage]
        known = [v for v in values if isinstance(v, (int, float)) and not isinstance(v, bool)]
        complete = bool(usage) and len(known) == len(usage)
        known_total = round(sum(known), 8) if known else None
        estimate_status = "complete" if complete else "incomplete" if known else "unknown"
        reason = (ended or {}).get("reason")
        mint_status = mint.get("status")
        mint_failed = isinstance(mint_status, int) and mint_status >= 400
        failed = mint_failed or bool(reason and any(
            word in str(reason).lower() for word in ("fail", "error", "denied", "refused")
        ))
        call_status = "failed" if failed else "ended" if ended else "active" if connected or usage else "started"
        versions = sorted({(d.get("estimate") or {}).get("pricing_version") for d in usage
                           if (d.get("estimate") or {}).get("pricing_version")})
        out[room] = {
            "room": room,
            "call_status": call_status,
            "end_reason": reason,
            "estimate_status": estimate_status,
            "estimated_usd": known_total if complete else None,
            "known_estimated_usd": known_total,
            "pricing_version": versions[0] if len(versions) == 1 else "mixed" if versions else None,
            "environment": _environment(mint.get("provenance")),
            "recorded_at": mint.get("recorded_at"),
            "usage_receipts": len(usage),
        }
    return out


def _read_latest(rooms):
    receipts = ledger().db.receipts
    projection = {"_id": 0, "kind": 1, "recorded_at": 1, "session_id": 1, "session_secret_fp": 1,
                  "reason": 1, "billable_activity": 1, "counted": 1, "estimate": 1, "provenance": 1}
    mints = list(receipts.find({"kind": "session_token_minted", "provenance.room": {"$in": rooms}}, projection)
                 .sort("recorded_at", -1))
    latest_ids = []
    secret_fps = []
    seen = set()
    for mint in mints:
        room = str(((mint.get("provenance") or {}).get("room")) or "")
        if room in seen:
            continue
        seen.add(room)
        if mint.get("session_id"):
            latest_ids.append(mint["session_id"])
        if mint.get("session_secret_fp"):
            secret_fps.append(mint["session_secret_fp"])
    clauses = []
    if latest_ids:
        clauses.append({"session_id": {"$in": latest_ids}})
    if secret_fps:
        clauses.append({"kind": "session_connected", "session_secret_fp": {"$in": secret_fps}})
    related = list(receipts.find({"$or": clauses}, projection)) if clauses else []
    return summarize_latest_calls(rooms, mints, related)


@router.get("/latest-by-room")
async def latest_by_room(user=Depends(require_admin)):
    """Latest call attempt and its evidence-backed estimate for every current room."""
    rooms = [str(room) for room in await db.residents.distinct("room") if room not in (None, "")]
    return {"rooms": await asyncio.to_thread(_read_latest, rooms)}
