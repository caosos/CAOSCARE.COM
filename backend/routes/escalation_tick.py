"""The one escalation authority (ENGINEERING_CONTRACT decision 8).

`run_tick()` is the only code that raises an alert's `escalation_level`. It
runs from the admin endpoint (`POST /escalation/tick`) and from the backend
schedule in routes/escalation_schedule.py (started in the server lifespan) -
independent of any simulator.

Rules, per alert:
  * only unresolved, unacknowledged alerts escalate; stale (> STALE_ALERT_HOURS)
    test debris is never escalated;
  * thresholds come from the facility's EscalationRule (level_2/level_3 seconds);
  * the level change is one atomic conditional update, so concurrent ticks
    (two workers, endpoint + schedule) escalate each alert once per level;
  * every change appends a NEW receipt (actor system:escalation, rule used,
    before/after level). Unclaimed Nursing requests are flagged once from
    here too (task_unclaimed_escalation.py). `Alert.status`, `aria_state` and `live_line_state`
    are not touched - they answer different questions.
"""
import logging
from datetime import datetime, timezone

from deps import db
from models import EscalationRule
from routes.ops_overview_util import alert_is_stale, parse_dt
from routes.notification_delivery import alert_provenance_flag, notify_alert_phone
from routes.receipts import create_receipt

log = logging.getLogger(__name__)

ACTOR_ID = "system:escalation"
_OPEN_STATUSES = ["open", "active", "escalated"]  # not "acknowledged"/"resolved"
_LIVING_COMMUNITY_SCOPE = "living_community"
_LIVING_COMMUNITY_ID = "sim:community:living-80-v1"


def outside_living_community_filter() -> dict:
    """Mongo filter that excludes only the exact protected community marker.

    Demo and other simulated records remain eligible for the normal escalation
    service.  A fresh object is returned because callers compose this into
    separate selection and atomic-update queries.
    """
    return {"$nor": [{
        "simulated": True,
        "simulation_scope": _LIVING_COMMUNITY_SCOPE,
        "simulation_community_id": _LIVING_COMMUNITY_ID,
    }]}


async def _living_community_resident_ids() -> tuple[str, ...]:
    """Derive protected identities from resident truth, not alert input."""
    rows = await db.residents.find(
        {
            "synthetic": True,
            "simulation_scope": _LIVING_COMMUNITY_SCOPE,
            "simulation_community_id": _LIVING_COMMUNITY_ID,
        },
        {"_id": 0, "resident_id": 1},
    ).to_list(1000)
    return tuple(sorted({row["resident_id"] for row in rows if row.get("resident_id")}))


def rule_for(rules_by_fac: dict, facility_id) -> dict:
    """The facility's own EscalationRule, or the safe defaults when it has none.
    Alerts and unclaimed requests both select their rule here."""
    return rules_by_fac.get(facility_id) or EscalationRule(facility_id=facility_id).model_dump()


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
    protected_resident_ids = await _living_community_resident_ids()
    rules_by_fac: dict = {}
    async for r in db.escalation_rules.find({}, {"_id": 0}):
        rules_by_fac[r.get("facility_id")] = r

    active = await db.alerts.find(
        {"status": {"$in": _OPEN_STATUSES}, "acknowledged_at": None, "resolved_at": None,
         "resident_id": {"$nin": list(protected_resident_ids)}},
        {"_id": 0},
    ).to_list(1000)

    out = {"escalated_to_2": 0, "escalated_to_3": 0, "skipped": 0, "stale_skipped": 0,
           "examined": len(active)}
    for a in active:
        rule = rule_for(rules_by_fac, a.get("facility_id"))
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
             "acknowledged_at": None, "resolved_at": None, "status": {"$in": _OPEN_STATUSES},
             "resident_id": {"$nin": list(protected_resident_ids)}},
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
    from routes.task_unclaimed_escalation import escalate_unclaimed
    out.update(await escalate_unclaimed(now, rules_by_fac))
    from routes.task_recurrence import generate   # recurring work occurrences ride the same tick
    try:
        out.update(await generate())
    except Exception as e:
        log.warning("recurrence generation failed: %s", e)
    return out


async def _try_sms(to_phone: str, alert: dict, level: int, rule: dict):
    """SMS through the one provider path; recorded and receipted either way."""
    body = (f"CAOS Care escalation: {alert.get('severity', 'alert')} in room "
            f"{alert.get('room', '?')}. Open the dashboard.")
    await notify_alert_phone(
        "sms", to_phone, body, alert, actor_id=ACTOR_ID,
        authority=f"escalation_rule:{rule.get('facility_id') or 'default'}:level_{level}",
        simulation=await alert_provenance_flag(alert))
