"""Approved-sender allowlist for the inbound email adapter, per department
lane ("menu", "activities" - extend EmailAllowlistLane in models.py for a
future department rather than hardcoding a third lane here).

Fail-closed by design: a lane with zero active entries has no approved
senders, so every inbound email to it is quarantined rather than treated
as approved by omission. This is deliberately a small, admin-managed list
rather than "any @facilitydomain.com address" inferred from somewhere else
- Michael (or whoever owns Admin) decides who can publish to the public
menu/activities calendar via email, the same way staff decide who can
publish to it via the dev-test endpoint (any authenticated staff/admin/
owner user - the allowlist is the equivalent gate for the unauthenticated
email channel).
"""
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends

from models import EmailAllowlistEntry, EmailAllowlistEntryCreate, EmailAllowlistLane
from deps import db, require_admin

router = APIRouter(prefix="/email/allowlist", tags=["email-inbound"])


def _normalize(addr: str) -> str:
    return (addr or "").strip().lower()


async def check_sender_allowed(lane: EmailAllowlistLane, from_address: str) -> bool:
    """True only if an ACTIVE allowlist entry for this lane matches the
    sender - either an exact address or a "@domain.com" suffix. No
    entries configured for the lane -> always False (fail closed)."""
    sender = _normalize(from_address)
    if not sender or "@" not in sender:
        return False
    domain_suffix = "@" + sender.split("@", 1)[1]
    entries = await db.email_allowlist.find(
        {"lane": lane, "active": True}, {"_id": 0, "pattern": 1},
    ).to_list(500)
    for e in entries:
        pattern = _normalize(e.get("pattern", ""))
        if not pattern:
            continue
        if pattern.startswith("@"):
            if domain_suffix == pattern:
                return True
        elif pattern == sender:
            return True
    return False


@router.get("")
async def list_allowlist(lane: Optional[EmailAllowlistLane] = None, user=Depends(require_admin)):
    q = {"lane": lane} if lane else {}
    items = await db.email_allowlist.find(q, {"_id": 0}).sort("created_at", -1).to_list(500)
    for i in items:
        v = i.get("created_at")
        if v and not isinstance(v, str):
            i["created_at"] = v.isoformat()
    return items


@router.post("")
async def add_allowlist_entry(body: EmailAllowlistEntryCreate, user=Depends(require_admin)):
    entry = EmailAllowlistEntry(
        lane=body.lane, pattern=_normalize(body.pattern), label=body.label,
        created_by=user["user_id"],
    )
    doc = entry.model_dump()
    doc["created_at"] = doc["created_at"].isoformat()
    await db.email_allowlist.insert_one(dict(doc))
    doc.pop("_id", None)
    return doc


@router.delete("/{entry_id}")
async def remove_allowlist_entry(entry_id: str, user=Depends(require_admin)):
    """Soft-disable, not a hard delete - matches Department's own
    active-flag pattern so the entry stays visible in history/audit."""
    result = await db.email_allowlist.update_one(
        {"entry_id": entry_id}, {"$set": {"active": False}},
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Allowlist entry not found")
    return {"ok": True}
