"""Auto-escalation + memory sanitize.

Escalation rule CRUD, an on-demand escalation tick (logic and schedule live
in routes/escalation_tick.py) and the PII sanitize task for archived
conversation turns.
"""
import re
import logging

from fastapi import APIRouter, Depends, HTTPException

from deps import db, require_admin, require_owner
from models import EscalationRule, now_utc
from routes.escalation_tick import run_tick

router = APIRouter(prefix="/escalation", tags=["escalation"])
log = logging.getLogger(__name__)


def _iso(doc: dict) -> dict:
    for k in ("created_at", "updated_at", "acknowledged_at", "resolved_at"):
        v = doc.get(k)
        if v and not isinstance(v, str):
            doc[k] = v.isoformat()
    return doc


# ---------------- Escalation rule CRUD ----------------

@router.get("/rule")
async def get_rule(facility_id: str | None = None, user=Depends(require_admin)):
    """Read the escalation rule for a facility (or default if no facility)."""
    rule = await db.escalation_rules.find_one(
        {"facility_id": facility_id}, {"_id": 0},
    )
    if not rule:
        # Return defaults — don't 404, the UI wants something to render.
        return EscalationRule(facility_id=facility_id).model_dump()
    return _iso(rule)


@router.put("/rule")
async def upsert_rule(rule: EscalationRule, user=Depends(require_admin)):
    rule.updated_at = now_utc()
    doc = rule.model_dump()
    doc["updated_at"] = doc["updated_at"].isoformat()
    await db.escalation_rules.update_one(
        {"facility_id": rule.facility_id}, {"$set": doc}, upsert=True,
    )
    return doc


# ---------------- Auto-escalation tick ----------------

@router.post("/tick")
async def tick(user=Depends(require_admin)):
    """Run one escalation pass now. The same function the backend schedule
    runs (routes/escalation_tick.py) - the only escalation authority."""
    return await run_tick()


# ---------------- Memory sanitize (owner-only) ----------------

# Conservative PII patterns. We don't try to find names — Claude Haiku
# extracted them on purpose (they're durable identity, not PII to redact).
# We DO redact obvious sensitive patterns from archived conversation turns.
_PATTERNS = [
    (re.compile(r"\b\d{3}[-\.\s]?\d{2}[-\.\s]?\d{4}\b"), "[SSN-REDACTED]"),
    (re.compile(r"\b(?:\+?1[-\.\s]?)?\(?\d{3}\)?[-\.\s]?\d{3}[-\.\s]?\d{4}\b"), "[PHONE-REDACTED]"),
    (re.compile(r"\b\d{1,5}\s+\w+\s+(?:Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Drive|Dr|Lane|Ln)\b", re.I), "[ADDRESS-REDACTED]"),
    (re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"), "[EMAIL-REDACTED]"),
    (re.compile(r"\b(?:\d[ -]*?){13,16}\b"), "[CARD-REDACTED]"),
]


@router.post("/memory/sanitize")
async def sanitize_old_turns(older_than_days: int = 30, dry_run: bool = False, user=Depends(require_owner)):
    """Owner-only. Walks every conversation turn older than `older_than_days`
    and redacts obvious PII patterns. Doesn't touch the bins (those are
    durable identity, not PII to redact). Returns a count."""
    from datetime import timedelta
    cutoff = (now_utc() - timedelta(days=older_than_days)).isoformat()
    cur = db.conversations.find(
        {"created_at": {"$lt": cutoff}, "sanitized": {"$ne": True}},
        {"_id": 0, "session_id": 1, "created_at": 1, "content": 1, "_internal_id": 1},
    )
    examined = redacted = 0
    async for turn in cur:
        examined += 1
        original = turn.get("content") or ""
        cleaned = original
        for rx, sub in _PATTERNS:
            cleaned = rx.sub(sub, cleaned)
        if cleaned != original:
            redacted += 1
            if not dry_run:
                await db.conversations.update_one(
                    {"session_id": turn["session_id"], "created_at": turn["created_at"]},
                    {"$set": {"content": cleaned, "sanitized": True, "sanitized_at": now_utc().isoformat()}},
                )
        elif not dry_run:
            await db.conversations.update_one(
                {"session_id": turn["session_id"], "created_at": turn["created_at"]},
                {"$set": {"sanitized": True}},
            )
    return {"examined": examined, "redacted": redacted, "dry_run": dry_run}
