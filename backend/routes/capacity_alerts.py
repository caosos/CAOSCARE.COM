"""Capacity alerts: one record per metric while it is above a level.

Levels NORMAL < WATCH < ACTION_NEEDED < CRITICAL (thresholds are fractions
of the metric's tested safe value, capacity_model.DEFAULT_CONFIG).

- Open: the metric has been at WATCH or above for `sustain_samples` samples
  in a row, and the same metric was not resolved within `cooldown_s` at the
  same or a higher level.
- Escalate: a higher level held for its sustain count. Never de-escalates
  in place; it either stays or resolves.
- Resolve (automatic): below the alert's level threshold minus
  `clear_margin` for `clear_samples` samples in a row. Manual resolution
  needs written evidence; if the metric is still above the threshold it
  also needs the action taken (capacity added / configuration changed).

Every opening, escalation, recommendation, acknowledgment, capacity change
and resolution writes a receipt (related_object_type "capacity_alert"),
chained to the alert's opening receipt.
"""
from typing import Optional

from deps import db
from models import uid
from routes.capacity_model import LEVELS, METRICS, attribution, level_for, now_iso, recommendation, values
from routes.receipts import create_receipt

SYSTEM_ACTOR = {"actor_id": "system:capacity_monitor", "actor_type": "system", "identity_basis": "system",
                "channel": "system", "actor_name": "capacity_monitor", "actor_role": "system"}


def _rank(level):
    return LEVELS.index(level)


async def _receipt(alert: dict, action: str, *, actor: dict, before: dict, after: dict, result: str,
                   evidence: dict, next_state: str) -> dict:
    rid = uid("rcpt")
    r = await create_receipt(
        action_type=action, related_object_type="capacity_alert", related_object_id=alert["alert_id"],
        source="system", status="completed", result=result[:300], receipt_id=rid,
        provenance={**actor, "authority": actor.get("authority", "system:capacity_monitor"),
                    "parent_receipt_id": alert.get("last_receipt_id"),
                    "correlation_id": alert.get("origin_receipt_id") or rid,
                    "before_state": before, "after_state": after, "result_label": "verified",
                    "next_state": next_state, "evidence": evidence})
    upd = {"last_receipt_id": rid}
    if not alert.get("origin_receipt_id"):
        upd["origin_receipt_id"] = rid
    await db.capacity_alerts.update_one({"alert_id": alert["alert_id"]}, {"$set": upd})
    alert.update(upd)
    return r


def _sustained_level(series: list, config: dict) -> str:
    """Highest level held for its sustain count at the end of the series."""
    best = "NORMAL"
    for name in ("WATCH", "ACTION_NEEDED", "CRITICAL"):
        n = config["sustain_samples"][name]
        tail = series[-n:]
        if len(tail) == n and all(u is not None and u >= config["levels"][name] for u in tail):
            best = name
    return best


def _evidence(key, sample, u, config, attr):
    vals = values(sample)
    return {"metric": key, "measured_value": vals.get(key), "tested_safe_value": config["safe"].get(key),
            "unit": METRICS[key][1], "utilization": u, "safe_value_source": METRICS[key][3],
            "remaining_headroom": round(config["safe"][key] - vals[key], 2) if vals.get(key) is not None else None,
            "sample_id": sample.get("sample_id"), "sample_at": sample.get("at"), **attr}


async def evaluate(samples: list, config: dict, now: Optional[str] = None) -> list:
    """samples: recent capacity samples, oldest first, each with a precomputed
    `utilization` dict. Returns the actions taken (for logs and tests)."""
    now = now or now_iso()
    if not samples:
        return []
    actions, latest = [], samples[-1]
    for key in METRICS:
        series = [s["utilization"].get(key) for s in samples]
        current = series[-1]
        target = _sustained_level(series, config)
        attr = attribution(latest, key)
        alert = await db.capacity_alerts.find_one({"metric": key, "status": {"$in": ["open", "acknowledged"]}},
                                                  {"_id": 0})
        ev = _evidence(key, latest, current, config, attr)
        if alert:
            if _rank(target) > _rank(alert["level"]):
                before = {"level": alert["level"]}
                await db.capacity_alerts.update_one({"alert_id": alert["alert_id"]}, {"$set": {
                    "level": target, "escalated_at": now, "measured_value": ev["measured_value"],
                    "utilization": current}})
                await _receipt(alert, "capacity_alert_escalated", actor=SYSTEM_ACTOR, before=before,
                               after={"level": target}, result=f"{key} {alert['level']} -> {target}",
                               evidence=ev, next_state="awaiting_acknowledgment")
                alert["level"] = target
                actions.append(("escalated", key, target))
            clear_at = config["levels"][alert["level"]] - config["clear_margin"]
            tail = series[-config["clear_samples"]:]
            if len(tail) == config["clear_samples"] and all(u is not None and u < clear_at for u in tail):
                await _resolve(alert, now, SYSTEM_ACTOR, f"{key} below {clear_at:.2f} of safe value for "
                               f"{config['clear_samples']} samples", ev, automatic=True)
                actions.append(("resolved", key, alert["level"]))
                continue
            await _maybe_recommend(alert, key, attr, now, config, ev, actions)
            continue
        if _rank(target) < _rank("WATCH"):
            continue
        last = await db.capacity_alerts.find_one({"metric": key, "status": "resolved"}, {"_id": 0},
                                                 sort=[("resolved_at", -1)])
        if last and _rank(target) <= _rank(last["level"]) and _age_s(last["resolved_at"], now) < config["cooldown_s"]:
            actions.append(("cooldown", key, target))
            continue
        alert = {"alert_id": uid("capalert"), "metric": key, "component": METRICS[key][0], "level": target,
                 "status": "open", "opened_at": now, "measured_value": ev["measured_value"],
                 "tested_safe_value": ev["tested_safe_value"], "unit": ev["unit"], "utilization": current,
                 "traffic_class": attr["traffic_class"], "simulated": attr["simulated"],
                 "recommendation": None, "acknowledged_by": None, "acknowledged_at": None,
                 "resolved_at": None, "resolution": None, "origin_receipt_id": None, "last_receipt_id": None,
                 "telemetry": {"sample_id": latest.get("sample_id"), "source": "capacity_samples"}}
        await db.capacity_alerts.insert_one(dict(alert))
        await _receipt(alert, "capacity_alert_opened", actor=SYSTEM_ACTOR, before={"level": "NORMAL"},
                       after={"level": target, "status": "open"}, result=f"{key} at {target}",
                       evidence=ev, next_state="awaiting_acknowledgment")
        actions.append(("opened", key, target))
        await _maybe_recommend(alert, key, attr, now, config, ev, actions)
    return actions


def _age_s(iso_then: str, iso_now: str) -> float:
    from datetime import datetime
    return (datetime.fromisoformat(iso_now) - datetime.fromisoformat(iso_then)).total_seconds()


async def _maybe_recommend(alert, key, attr, now, config, ev, actions):
    rec = recommendation(key, alert["level"], attr, _age_s(alert["opened_at"], now), config)
    if not rec["type"] or (alert.get("recommendation") or {}).get("type") == rec["type"]:
        return
    rec["issued_at"] = now
    await db.capacity_alerts.update_one({"alert_id": alert["alert_id"]}, {"$set": {"recommendation": rec}})
    await _receipt(alert, "capacity_recommendation_issued", actor=SYSTEM_ACTOR,
                   before={"recommendation": (alert.get("recommendation") or {}).get("type")},
                   after={"recommendation": rec["type"]}, result=rec["text"], evidence=ev,
                   next_state="awaiting_action")
    alert["recommendation"] = rec
    actions.append(("recommended", key, rec["type"]))


async def _resolve(alert, now, actor, reason, evidence, automatic=False, action_taken=None):
    before = {"status": alert["status"], "level": alert["level"]}
    resolution = {"reason": reason, "automatic": automatic, "action_taken": action_taken,
                  "by": actor.get("actor_id"), "evidence": evidence}
    await db.capacity_alerts.update_one({"alert_id": alert["alert_id"]}, {"$set": {
        "status": "resolved", "resolved_at": now, "resolution": resolution}})
    await _receipt(alert, "capacity_alert_resolved", actor=actor, before=before,
                   after={"status": "resolved", "level": alert["level"]}, result=reason, evidence=evidence,
                   next_state="closed")


def user_actor(user: dict) -> dict:
    return {"actor_id": user["user_id"], "actor_type": "real-human", "identity_basis": "authenticated",
            "channel": "staff_ui", "actor_name": user.get("name"), "actor_role": user.get("role"),
            "authority": f"admin:{user.get('role')}"}


async def acknowledge(alert_id: str, user: dict, note: str = "") -> dict:
    alert = await db.capacity_alerts.find_one({"alert_id": alert_id}, {"_id": 0})
    if not alert or alert["status"] != "open":
        return {"ok": False, "detail": "alert is not open"}
    now = now_iso()
    await db.capacity_alerts.update_one({"alert_id": alert_id}, {"$set": {
        "status": "acknowledged", "acknowledged_by": user.get("name") or user["user_id"], "acknowledged_at": now}})
    await _receipt(alert, "capacity_alert_acknowledged", actor=user_actor(user), before={"status": "open"},
                   after={"status": "acknowledged"}, result=note or "acknowledged", evidence={"note": note},
                   next_state="awaiting_resolution")
    return {"ok": True}


async def resolve_manually(alert_id: str, user: dict, evidence_note: str, current_utilization: Optional[float],
                           config: dict, action_taken: Optional[str] = None) -> dict:
    """No resolution without evidence: a note is always required; if the
    metric is still at or above the alert's level, the action taken must be
    stated and is recorded as its own receipt."""
    alert = await db.capacity_alerts.find_one({"alert_id": alert_id}, {"_id": 0})
    if not alert or alert["status"] == "resolved":
        return {"ok": False, "detail": "alert is not open"}
    if not (evidence_note or "").strip():
        return {"ok": False, "detail": "evidence is required to resolve a capacity alert"}
    still_high = current_utilization is not None and level_for(current_utilization, config) != "NORMAL" \
        and _rank(level_for(current_utilization, config)) >= _rank(alert["level"])
    if still_high and not (action_taken or "").strip():
        return {"ok": False, "detail": "the metric is still at this level; state the action taken "
                                       "(capacity added or configuration changed)"}
    actor = user_actor(user)
    if action_taken:
        await _receipt(alert, "capacity_added_or_configuration_changed", actor=actor, before={},
                       after={"action_taken": action_taken}, result=action_taken,
                       evidence={"note": evidence_note}, next_state="verify_after_change")
    await _resolve(alert, now_iso(), actor, evidence_note,
                   {"current_utilization": current_utilization, "note": evidence_note}, action_taken=action_taken)
    return {"ok": True, "still_high_at_resolution": still_high}
