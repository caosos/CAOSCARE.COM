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
    before/after level). Unclaimed Nursing requests are flagged once from
    here too (task_unclaimed_escalation.py). `Alert.status`, `aria_state` and `live_line_state`
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
    rules_by_fac: dict = {}
    async for r in db.escalation_rules.find({}, {"_id": 0}):
        rules_by_fac[r.get("facility_id")] = r

    active = await db.alerts.find(
        {"status": {"$in": _OPEN_STATUSES}, "acknowledged_at": None, "resolved_at": None},
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


_HEALTH = {"type": "escalation_schedule", "id": "default"}
_health_state: dict = {}   # in-process cache of the latest health receipt; loaded from receipts once
_ACTION = {"failing": "escalation_tick_failed", "healthy": "escalation_tick_recovered",
           "disabled": "escalation_schedule_disabled"}
_STATE_OF = {v: k for k, v in _ACTION.items()}
_RESULT = {"failing": "escalation tick failed; alerts stay open on the dashboard but are not escalated",
           "healthy": "escalation tick running",
           "disabled": "escalation schedule switched off at startup; alerts stay open on the dashboard but are not escalated"}
_schedule: dict = {"task": None, "interval": None, "last_tick_at": None}   # this process's loop


async def _latest_health() -> dict:
    if "state" not in _health_state:
        last = await db.receipts.find_one(
            {"related_object_type": _HEALTH["type"], "related_object_id": _HEALTH["id"]},
            {"_id": 0, "receipt_id": 1, "action_type": 1}, sort=[("created_at", -1)])
        _health_state.update(state=_STATE_OF.get((last or {}).get("action_type"), "healthy"),
                             receipt_id=(last or {}).get("receipt_id"))
    return _health_state


async def _record_health(after: str, *, error: str | None = None, result: dict | None = None,
                         authority: str = "escalation_schedule") -> None:
    """Only a change of state is receipted (healthy / failing / disabled), so a
    tick that keeps failing, or a restart that stays switched off, leaves one
    record, not thousands."""
    h = await _latest_health()
    if h["state"] == after:
        return
    detail = {"error": error} if after == "failing" else {"tick_result": result} if result else {}
    rcpt = await create_receipt(
        action_type=_ACTION[after], related_object_type=_HEALTH["type"], related_object_id=_HEALTH["id"],
        source="system", status="failed" if after == "failing" else "completed",
        result=_RESULT[after], failure_reason=error,
        provenance={"actor_id": ACTOR_ID, "actor_type": "system", "actor_name": "Escalation tick",
                    "authority": authority,
                    "before_state": {"tick": h["state"]},
                    "after_state": {"tick": after, **detail},
                    "parent_receipt_id": h["receipt_id"],
                    "result_label": "failed" if after == "failing" else "verified",
                    "next_state": {"failing": "retry_next_interval", "healthy": "escalating",
                                   "disabled": "not_escalating_until_enabled"}[after]})
    h.update(state=after, receipt_id=rcpt["receipt_id"])


async def tick_once() -> None:
    """One scheduled pass: run the tick, and receipt a failure or a recovery."""
    _schedule["last_tick_at"] = datetime.now(timezone.utc)
    try:
        result = await run_tick()
    except asyncio.CancelledError:
        raise
    except Exception as e:
        log.warning("escalation tick failed: %s", e)
        try:
            await _record_health("failing", error=f"{type(e).__name__}: {e}"[:500])
        except Exception as e2:   # the receipt store itself may be what is down
            log.warning("could not record escalation tick failure: %s", e2)
        return
    try:
        await _record_health("healthy", result=result)
    except Exception as e:
        log.warning("could not record escalation tick recovery: %s", e)


async def run_escalation_loop(interval: int) -> None:
    """Background schedule. Never imports simulator code."""
    while True:
        await tick_once()
        await asyncio.sleep(interval)


async def start_schedule() -> asyncio.Task | None:
    """Called once from the server lifespan. Switched off -> receipted (once)
    and reported by /api/health; never silently absent."""
    interval = auto_interval_seconds()
    if interval is None:
        _schedule.update(task=None, interval=None)
        try:
            await _record_health("disabled", authority="env:CAOSCARE_ESCALATION_AUTO")
        except Exception as e:
            log.warning("could not record escalation schedule disabled: %s", e)
        return None
    _schedule.update(task=asyncio.create_task(run_escalation_loop(interval)), interval=interval,
                     last_tick_at=None, started_at=datetime.now(timezone.utc))
    return _schedule["task"]


def escalation_status(now: datetime | None = None) -> dict:
    """Read-only: what /api/health reports. Only "running" means escalation is happening."""
    now = now or datetime.now(timezone.utc)
    task, interval, last = _schedule["task"], _schedule["interval"], _schedule["last_tick_at"]
    if task is None:
        state = "disabled"
    elif task.done():
        state = "stopped"
    elif last is None:
        state = "starting"
    elif (now - last).total_seconds() > 3 * interval + 60:
        state = "stale"
    elif _health_state.get("state") == "failing":
        state = "failing"
    else:
        state = "running"
    return {"state": state, "interval_seconds": interval, "last_tick_at": last.isoformat() if last else None}
