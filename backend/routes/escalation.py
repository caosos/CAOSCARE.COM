"""Auto-escalation + memory sanitize.

Two background-style tasks exposed as endpoints (so cron / k8s CronJob /
the user can fire them on demand). The escalation tick polls active alerts
and bumps their severity / fires notifications when staff hasn't ack'd in
time. The sanitize task scrubs PII from archived conversation turns.
"""
from datetime import datetime, timezone
import re
import logging

from fastapi import APIRouter, Depends, HTTPException

from deps import db, require_admin, require_owner
from models import EscalationRule, now_utc

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
    """Run one escalation pass over all active alerts. Idempotent — alerts
    that have already been escalated to a level past the rule's threshold
    are skipped. Fire from a cron every 30s in production, or hit it
    manually for testing."""
    now = datetime.now(timezone.utc)
    rules_cur = db.escalation_rules.find({}, {"_id": 0})
    rules_by_fac: dict = {}
    async for r in rules_cur:
        rules_by_fac[r.get("facility_id")] = r
    default_rule = EscalationRule().model_dump()

    active = await db.alerts.find(
        {"status": {"$in": ["open", "active", "acknowledged", "escalated"]}},
        {"_id": 0},
    ).to_list(1000)

    actions = {"escalated_to_2": 0, "escalated_to_3": 0, "skipped": 0, "examined": len(active)}
    for a in active:
        rule = rules_by_fac.get(a.get("facility_id"), default_rule)
        if not rule.get("enabled", True):
            actions["skipped"] += 1
            continue
        # Already at level 3? Nothing to do.
        if a.get("escalation_level", 1) >= 3:
            actions["skipped"] += 1
            continue
        created = a.get("created_at")
        if isinstance(created, str):
            created = datetime.fromisoformat(created.replace("Z", "+00:00"))
        if created is None:
            continue
        elapsed = (now - created.replace(tzinfo=timezone.utc) if created.tzinfo is None else now - created).total_seconds()

        # Skip if staff already acknowledged
        if a.get("acknowledged_at"):
            actions["skipped"] += 1
            continue

        new_level = a.get("escalation_level", 1)
        if elapsed >= rule.get("level_3_seconds", 150) and new_level < 3:
            new_level = 3
            actions["escalated_to_3"] += 1
        elif elapsed >= rule.get("level_2_seconds", 90) and new_level < 2:
            new_level = 2
            actions["escalated_to_2"] += 1

        if new_level > a.get("escalation_level", 1):
            event = {
                "type": "escalation",
                "level": new_level,
                "at": now.isoformat(),
                "rule_id": rule.get("facility_id") or "default",
            }
            await db.alerts.update_one(
                {"alert_id": a["alert_id"]},
                {
                    "$set": {"escalation_level": new_level, "status": "escalated"},
                    "$push": {"timeline": event},
                },
            )
            # Hook for SMS/email — gracefully no-op when keys absent
            try:
                if new_level >= 3 and rule.get("notify_oncall_phone"):
                    await _try_sms(rule["notify_oncall_phone"], a)
                if new_level >= 2 and rule.get("notify_supervisor_phone"):
                    await _try_sms(rule["notify_supervisor_phone"], a)
            except Exception as e:
                log.warning(f"escalation notify failed: {e}")

    return actions


async def _try_sms(to_phone: str, alert: dict):
    """Best-effort SMS — uses Twilio if creds in env, otherwise just logs.
    Real Twilio integration plugs in here once the user provides keys."""
    sid = __import__("os").environ.get("TWILIO_ACCOUNT_SID")
    token = __import__("os").environ.get("TWILIO_AUTH_TOKEN")
    from_phone = __import__("os").environ.get("TWILIO_FROM_PHONE")
    if not (sid and token and from_phone):
        log.info(f"[escalation] would SMS {to_phone}: alert {alert.get('alert_id')} (Twilio not configured)")
        return
    # Lazy import — only when we actually have keys
    try:
        from twilio.rest import Client  # type: ignore
        client = Client(sid, token)
        body = f"CAOS Care escalation: {alert.get('severity', 'alert')} in room {alert.get('room', '?')}. Open the dashboard."
        client.messages.create(to=to_phone, from_=from_phone, body=body)
    except Exception as e:
        log.warning(f"twilio send failed: {e}")


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
