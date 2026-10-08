"""The one escalation authority (ENGINEERING_CONTRACT decision 8).

`run_tick()` is the only code that raises an alert's `escalation_level`. It
runs from the admin endpoint (`POST /escalation/tick`) and from a backend
schedule started in the server lifespan - independent of any simulator.

Rules, per alert:
  * only unresolved, unacknowledged alerts escalate; stale (> STALE_ALERT_HOURS)
    test debris is never escalated;
  * thresholds come from the facility's EscalationRule (level_2/level_3 seconds);
  * the level change is one atomic conditional update, so concurrent ticks
    (two workers, endpoint + schedule) escalate each alert once per level;
  * every change appends a NEW receipt (actor system:escalation, rule used,
    before/after level). `Alert.status`, `aria_state` and `live_line_state`
    are not touched - they answer different questions.
"""
import asyncio
import logging
import os
from datetime import datetime, timezone

from deps import db
from models import EscalationRule
from routes.ops_overview_util import alert_is_stale, parse_dt
from routes.notification_delivery import alert_provenance_flag, notify_alert_phone
from routes.receipts import create_receipt

log = logging.getLogger(__name__)

ACTOR_ID = "system:escalation"
DEFAULT_INTERVAL_SECONDS = 30
_OPEN_STATUSES = ["open", "active", "escalated"]  # not "acknowledged"/"resolved"


def auto_interval_seconds() -> int | None:
    """Schedule interval from CAOSCARE_ESCALATION_INTERVAL; None = disabled
    (CAOSCARE_ESCALATION_AUTO=0)."""
    if os.environ.get("CAOSCARE_ESCALATION_AUTO", "1").strip().lower() in ("0", "false", "no", "off"):
        return None
    try:
        return max(5, int(os.environ.get("CAOSCARE_ESCALATION_INTERVAL", DEFAULT_INTERVAL_SECONDS)))
    except ValueError:
        return DEFAULT_INTERVAL_SECONDS


def _target_level(elapsed: float, rule: dict) -> int:
    if elapsed >= rule.get("level_3_seconds", 150):
        return 3
    if elapsed >= rule.get("level_2_seconds", 90):
        return 2
    return 0


async def _record(alert: dict, rule: dict, before: int, after: int, at: datetime) -> None:
    rule_id = rule.get("facility_id") or "default"
    thresholds = {"level_2_seconds": rule.get("level_2_seconds", 90),
                  "level_3_seconds": rule.get("level_3_seconds", 150)}
    await create_receipt(
        action_type="alert_escalated",
        related_object_type="alert",
        related_object_id=alert["alert_id"],
        source="system",
        resident_id=alert.get("resident_id"),
        room=alert.get("room"),
        zone=alert.get("zone"),
        status="completed",
        result=f"escalation level {before} -> {after}",
        provenance={
            "actor_id": ACTOR_ID, "actor_type": "system", "actor_name": "Escalation tick",
            "authority": f"escalation_rule:{rule_id}",
            "before_state": {"escalation_level": before},
            "after_state": {"escalation_level": after, "thresholds": thresholds,
                            "rule_id": rule_id, "at": at.isoformat()},
            "result_label": "verified",
            "next_state": "awaiting_staff_acknowledgement",
        },
    )


async def run_tick(now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    rules_by_fac: dict = {}
    async for r in db.escalation_rules.find({}, {"_id": 0}):
        rules_by_fac[r.get("facility_id")] = r
    default_rule = EscalationRule().model_dump()

    active = await db.alerts.find(
        {"status": {"$in": _OPEN_STATUSES}, "acknowledged_at": None, "resolved_at": None},
        {"_id": 0},
    ).to_list(1000)

    out = {"escalated_to_2": 0, "escalated_to_3": 0, "skipped": 0, "stale_skipped": 0,
           "examined": len(active)}
    for a in active:
        rule = rules_by_fac.get(a.get("facility_id"), default_rule)
        current = a.get("escalation_level") or 0
        if not rule.get("enabled", True) or current >= 3:
            out["skipped"] += 1
            continue
        if alert_is_stale(a, now):
            out["stale_skipped"] += 1
            continue
        created = parse_dt(a.get("created_at"))
        if created is None:
            out["skipped"] += 1
            continue
        target = _target_level((now - created).total_seconds(), rule)
        if target <= current:
            continue
        # Atomic claim: only one tick can move this alert past `current`.
        claimed = await db.alerts.update_one(
            {"alert_id": a["alert_id"],
             "$or": [{"escalation_level": {"$lt": target}}, {"escalation_level": None}],
             "acknowledged_at": None, "resolved_at": None, "status": {"$in": _OPEN_STATUSES}},
            {"$set": {"escalation_level": target, "escalated_at": now.isoformat(),
                      "escalation_source": ACTOR_ID},
             "$push": {"timeline": {"type": "escalation", "level": target, "from": current,
                                    "at": now.isoformat(), "rule_id": rule.get("facility_id") or "default"}}},
        )
        if claimed.modified_count == 0:
            continue
        out[f"escalated_to_{target}"] += 1
        try:
            await _record(a, rule, current, target, now)
            if target >= 3 and rule.get("notify_oncall_phone"):
                await _try_sms(rule["notify_oncall_phone"], a, target, rule)
            if target >= 2 and rule.get("notify_supervisor_phone"):
                await _try_sms(rule["notify_supervisor_phone"], a, target, rule)
        except Exception as e:
            log.warning("escalation side effect failed for %s: %s", a.get("alert_id"), e)
    return out


async def _try_sms(to_phone: str, alert: dict, level: int, rule: dict):
    """SMS through the one provider path; recorded and receipted either way."""
    body = (f"CAOS Care escalation: {alert.get('severity', 'alert')} in room "
            f"{alert.get('room', '?')}. Open the dashboard.")
    await notify_alert_phone(
        "sms", to_phone, body, alert, actor_id=ACTOR_ID,
        authority=f"escalation_rule:{rule.get('facility_id') or 'default'}:level_{level}",
        simulation=await alert_provenance_flag(alert))


async def run_escalation_loop(interval: int) -> None:
    """Background schedule. Never imports simulator code."""
    while True:
        try:
            await run_tick()
        except asyncio.CancelledError:
            raise
        except Exception as e:
            log.warning("escalation tick failed: %s", e)
        await asyncio.sleep(interval)
