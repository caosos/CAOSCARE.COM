"""Reconstruction endpoints for the activation observability log.

Answers "Why did Room 214 Aria wake at 03:21:43?" with one server-timestamp-
ordered evidence chain, merged from every store WITHOUT copying or mutating
any of them:

  * db.activation_events        (the correlated index this system adds)
  * db.rf_events                (raw RF frames + WHO/WHAT classification)
  * db.resident_aria_lease_events (room-lease claim/release)
  * db.realtime_diagnostics     (WebRTC / mic / VAD / transcript / session end)
  * db.alerts .event_log / .presses  (ResidentEvent lifecycle)

Authenticated read (transcript fragments appear in realtime_diagnostics).
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from deps import db, get_current_user
from models import now_utc
from datetime import datetime, timedelta

router = APIRouter(prefix="/activation-events", tags=["activation-observability"])


def _row(ts, layer, event, source, **kw):
    r = {"ts": ts, "layer": layer, "event": event, "source": source}
    r.update({k: v for k, v in kw.items() if v is not None})
    return r


async def _merge_for_alert(alert_id: str, activation_id: Optional[str]) -> list[dict]:
    rows: list[dict] = []
    alert = await db.alerts.find_one({"alert_id": alert_id}, {"_id": 0})
    if not alert:
        return rows
    activation_id = activation_id or alert.get("activation_id")
    room = alert.get("room")

    async for ae in db.activation_events.find(
        {"$or": [{"activation_id": activation_id} if activation_id else {"_id": None},
                 {"alert_id": alert_id}]}, {"_id": 0},
    ):
        rows.append(_row(ae["ts"], ae["layer"], ae["event"], "activation_events",
                         data=ae.get("data"), session_id=ae.get("session_id"),
                         kiosk_id=ae.get("kiosk_id"), client_instance_id=ae.get("client_instance_id"),
                         rf_device_id=ae.get("rf_device_id"), activation_id=ae.get("activation_id"),
                         ts_client=ae.get("ts_client")))

    # RF frames for this alert (+ a small pre-roll window so the triggering
    # burst is visible even if only its activation frame carries alert_id).
    rfq = {"$or": [{"alert_id": alert_id}]}
    dev = (alert.get("source_metadata") or {}).get("rf_device_id")
    created = alert.get("created_at")
    if dev and created:
        try:
            lo = (datetime.fromisoformat(created) - timedelta(hours=48)).isoformat()
            rfq["$or"].append({"matched_device_id": dev, "received_at": {"$gte": lo}})
        except Exception:
            pass
    async for e in db.rf_events.find(rfq, {"_id": 0}):
        fp = e.get("fingerprint") or {}
        rows.append(_row(e.get("received_at"), "rf", "frame_received", "rf_events",
                         data={"semantic_class": e.get("semantic_class"),
                               "allowed_activation": e.get("allowed_activation"),
                               "class_reasons": e.get("class_reasons"),
                               "class_evidence": e.get("class_evidence"),
                               "matched_device_id": e.get("matched_device_id"),
                               "match_score": e.get("match_score"),
                               "frequency_hz": fp.get("frequency_hz"),
                               "bit_pattern_hex": fp.get("bit_pattern_hex"),
                               "decoded": fp.get("decoded"), "rssi": fp.get("rssi"),
                               "captured_at": e.get("captured_at")},
                         alert_id=e.get("alert_id"), activation_id=e.get("activation_id"),
                         rf_device_id=e.get("matched_device_id")))

    # Room lease
    if room:
        async for le in db.resident_aria_lease_events.find({"lease.room": room}, {"_id": 0}):
            rows.append(_row(le.get("at"), "lease", le.get("event"), "resident_aria_lease_events",
                             data={"reason": le.get("reason"), "lease": le.get("lease")},
                             session_id=(le.get("lease") or {}).get("session_id")))

    # ResidentEvent lifecycle (embedded)
    for ev in alert.get("event_log", []):
        rows.append(_row(ev.get("at"), "resident_event", ev.get("field"), "alert.event_log",
                         data={"utterance": ev.get("utterance")},
                         session_id=ev.get("session_id"), activation_id=ev.get("activation_id")))
    for p in alert.get("presses", []):
        rows.append(_row(p.get("at"), "resident_event", "press_recorded", "alert.presses",
                         data={"source": p.get("source"), "rssi": p.get("rssi"),
                               "press_id": p.get("press_id")},
                         rf_device_id=p.get("device_id")))
    for esc in alert.get("escalations", []):
        rows.append(_row(esc.get("at"), "resident_event", "ai_escalation", "alert.escalations",
                         data={"source": esc.get("source"), "reason": esc.get("reason"),
                               "requested_department": esc.get("requested_department"),
                               "requested_severity": esc.get("requested_severity"),
                               "effective_severity": esc.get("effective_severity")},
                         session_id=esc.get("session_id"), activation_id=activation_id))

    # Staff page / dispatch - the durable proof behind "a nurse has been paged"
    async for sd in db.staff_dispatches.find({"alert_id": alert_id}, {"_id": 0}):
        for ev in sd.get("events", []):
            rows.append(_row(ev.get("at"), "dispatch", f"page_{ev.get('status')}", "staff_dispatches",
                             data={"dispatch_id": sd.get("dispatch_id"), "department": sd.get("department"),
                                   "severity": sd.get("severity"), "reason": sd.get("reason"),
                                   "delivery_mechanism": sd.get("delivery_mechanism"),
                                   "failure_reason": sd.get("failure_reason"),
                                   "receipt_id": sd.get("receipt_id"), "detail": ev.get("detail")},
                             alert_id=alert_id, activation_id=sd.get("activation_id"),
                             session_id=sd.get("session_id")))

    # Realtime diagnostics for every session_id referenced so far
    sids = {r.get("session_id") for r in rows if r.get("session_id")}
    sids.add(alert.get("aria_session_id"))
    for sid in {s for s in sids if s}:
        async for d in db.realtime_diagnostics.find({"session_id": sid}, {"_id": 0}):
            rows.append(_row(d.get("created_at"), "realtime", d.get("event_type"), "realtime_diagnostics",
                             data={"text": d.get("text"), "meta": d.get("meta"),
                                   "assistant_speaking": d.get("assistant_speaking")},
                             session_id=sid, activation_id=d.get("activation_id")))

    rows.sort(key=lambda r: (r.get("ts") or ""))
    return rows


@router.get("/{activation_id}")
async def timeline_by_activation(activation_id: str, user=Depends(get_current_user)):
    ae = await db.activation_events.find_one({"activation_id": activation_id}, {"_id": 0, "alert_id": 1})
    alert = await db.alerts.find_one({"activation_id": activation_id}, {"_id": 0, "alert_id": 1})
    alert_id = (alert or {}).get("alert_id") or (ae or {}).get("alert_id")
    if not alert_id:
        raise HTTPException(404, detail="No activation/alert found for that activation_id")
    return {"activation_id": activation_id, "alert_id": alert_id,
            "timeline": await _merge_for_alert(alert_id, activation_id)}


@router.get("/room/{room}/at")
async def timeline_by_room_time(
    room: str,
    at: str = Query(..., description="ISO timestamp of the wake to explain"),
    window_min: int = Query(30, ge=1, le=240),
    user=Depends(get_current_user),
):
    """For 'why did Room X wake at T' when you don't have the activation_id:
    find the activation cycle(s) whose events bracket [T-window, T+window]."""
    try:
        t = datetime.fromisoformat(at)
    except ValueError:
        raise HTTPException(400, detail="`at` must be an ISO timestamp")
    lo = (t - timedelta(minutes=window_min)).isoformat()
    hi = (t + timedelta(minutes=window_min)).isoformat()
    seen: dict[str, str] = {}
    async for ae in db.activation_events.find(
        {"room": room, "ts": {"$gte": lo, "$lte": hi}, "alert_id": {"$ne": None}},
        {"_id": 0, "alert_id": 1, "activation_id": 1},
    ):
        if ae.get("alert_id"):
            seen[ae["alert_id"]] = ae.get("activation_id")
    if not seen:
        alert = await db.alerts.find_one(
            {"room": room, "event_log.at": {"$gte": lo, "$lte": hi}},
            {"_id": 0, "alert_id": 1, "activation_id": 1}, sort=[("created_at", -1)],
        )
        if alert:
            seen[alert["alert_id"]] = alert.get("activation_id")
    out = []
    for alert_id, activation_id in seen.items():
        out.append({"alert_id": alert_id, "activation_id": activation_id,
                    "timeline": await _merge_for_alert(alert_id, activation_id)})
    return {"room": room, "at": at, "window_min": window_min, "activations": out}


@router.get("/rf-device/{rf_device_id}/recent")
async def rf_device_recent(rf_device_id: str, limit: int = Query(50, ge=1, le=500),
                           user=Depends(get_current_user)):
    """Every classified transmission from one paired device, newest first -
    WHO stays fixed, WHAT is the story. For diagnostics / protocol mapping."""
    dev = await db.rf_devices.find_one({"rf_device_id": rf_device_id}, {"_id": 0})
    if not dev:
        raise HTTPException(404, detail="RF device not found")
    frames = await db.rf_events.find(
        {"matched_device_id": rf_device_id}, {"_id": 0},
    ).sort("received_at", -1).to_list(limit)
    return {
        "device": {k: dev.get(k) for k in (
            "rf_device_id", "label", "resident_id", "room", "enabled",
            "last_seen_at", "last_transmission_at", "last_transmission_class",
            "press_count", "supervisory_count", "unknown_count", "tamper_count",
            "battery_status_count", "low_battery", "last_rssi")},
        "recent_transmissions": [
            {"received_at": f.get("received_at"), "semantic_class": f.get("semantic_class"),
             "allowed_activation": f.get("allowed_activation"), "class_reasons": f.get("class_reasons"),
             "match_score": f.get("match_score"), "alert_id": f.get("alert_id"),
             "switches": ((f.get("fingerprint") or {}).get("decoded") or {}),
             "rssi": (f.get("fingerprint") or {}).get("rssi")}
            for f in frames
        ],
    }
