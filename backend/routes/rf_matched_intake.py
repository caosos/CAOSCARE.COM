"""Matched-frame intake + semantics gate (Level 1 directive, 2026-09-07).

Split out of routes/rf.py (already over the 300-line cap). rf.py answers
WHO transmitted (fingerprint match); this module answers WHAT they
transmitted and decides whether it is allowed to become a resident help
activation.

For EVERY matched frame, regardless of class:
  * the raw db.rf_events row is still written by rf.py (evidence kept)
  * device health telemetry is updated (last_seen, RSSI, battery, per-class
    counters, last_transmission_class)
  * the frame is classified (routes/rf_semantics.classify_transmission)
  * the classification is stamped onto the rf_events row AND logged to the
    activation observability stream (routes/activation_log.alog)

ONLY `help_press` is passed to record_resident_activation(). supervisory /
tamper / battery_status / unknown update health + telemetry and are logged,
but never create/re-arm a ResidentEvent, never reset activation_consumed_at,
never claim a room lease, never wake Aria, never page staff.
"""
import logging

from deps import db
from models import now_utc
from routes.activation_log import alog
from routes.rf_semantics import classify_transmission, burst_context, ACTIVATION_CLASS

log = logging.getLogger(__name__)

_SEV_MAP = {"help": "assist", "assist": "assist", "emergency": "emergency", "comfort": "comfort"}
_CLASS_COUNTER = {
    "supervisory": "supervisory_count",
    "tamper": "tamper_count",
    "battery_status": "battery_status_count",
    "unknown": "unknown_count",
}


async def handle_matched_frame(device: dict, kiosk: dict, payload, raw_event: dict) -> dict:
    """Classify one matched frame, keep health current, gate activation.
    Mutates `raw_event` (the db.rf_events doc) in place with the WHAT fields
    and returns the bits rf.py needs for its JSON response."""
    rf_device_id = device["rf_device_id"]
    fp = payload.fingerprint.model_dump()
    now = now_utc()

    # ---- health telemetry: ALWAYS, every class -------------------------
    battery_ok = (fp.get("decoded") or {}).get("battery_ok")
    telemetry = {"last_seen_at": now.isoformat(), "last_rssi": fp.get("rssi"),
                 "last_transmission_at": now.isoformat()}
    if battery_ok is not None:
        telemetry["low_battery"] = not bool(battery_ok)

    # ---- classify -----------------------------------------------------
    ctx = await burst_context(db, rf_device_id, now=now)
    rfclass = classify_transmission(
        fp, matched=True,
        burst_frames=ctx["burst_frames"], burst_span_sec=ctx["burst_span_sec"],
        prior_same_device_gap_sec=ctx["prior_same_device_gap_sec"], device=device,
    )
    telemetry["last_transmission_class"] = rfclass.semantic
    raw_event.update(rfclass.as_dict())            # semantic_class / allowed_activation / reasons / evidence
    raw_event["rf_device_id"] = rf_device_id       # WHO, alongside WHAT, on the raw row

    resident_id = device.get("resident_id")
    room = device.get("room") or kiosk.get("room")

    inc = {}
    if rfclass.semantic in _CLASS_COUNTER:
        inc[_CLASS_COUNTER[rfclass.semantic]] = 1
        telemetry[f"last_{rfclass.semantic}_at"] = now.isoformat()
    if inc:
        await db.rf_devices.update_one({"rf_device_id": rf_device_id}, {"$set": telemetry, "$inc": inc})
    else:
        await db.rf_devices.update_one({"rf_device_id": rf_device_id}, {"$set": telemetry})

    await alog(
        "rf", "frame_classified", room=room, resident_id=resident_id, rf_device_id=rf_device_id,
        kiosk_id=payload.kiosk_id,
        data={
            "semantic_class": rfclass.semantic,
            "allowed_activation": rfclass.allows_activation,
            "reasons": rfclass.reasons,
            "evidence": rfclass.evidence,
            "match_score": raw_event.get("match_score"),
            "sequence": payload.sequence,
        },
    )

    out = {
        "semantic_class": rfclass.semantic,
        "allowed_activation": rfclass.allows_activation,
        "class_reasons": rfclass.reasons,
        "alert_id": None, "activation_id": None,
        "press_coalesced": False, "echo_frame": False,
    }

    # ---- NON-help: stop here. Health updated, evidence kept, logged. --
    if rfclass.semantic != ACTIVATION_CLASS:
        await alog(
            "rf", "activation_suppressed", room=room, resident_id=resident_id, rf_device_id=rf_device_id,
            data={"semantic_class": rfclass.semantic, "reasons": rfclass.reasons,
                  "would_have_matched_device": rf_device_id},
        )
        return out

    # ---- help_press: the ONLY path into the activation pipeline. Hand
    # off to routes/rf_activation_intake.record_matched_frame - the
    # concurrency-safe 2s-idle burst grouping + record_resident_activation
    # already running in ~/CAOSCARE.COM. This gate does not re-implement
    # frame collapsing (that would duplicate the burst-id mechanism);
    # it only decides WHETHER the frame is allowed in.
    try:
        from routes.rf_activation_intake import record_matched_frame
        coalesced = await record_matched_frame(device, kiosk, payload, raw_event)
        out["alert_id"] = raw_event.get("alert_id")
        out["press_coalesced"] = coalesced
        # record_matched_frame sets raw_event["press_counted"]: False means
        # this frame was a repeat within the burst window (our "echo").
        out["echo_frame"] = raw_event.get("press_counted") is False
        if out["alert_id"]:
            a = await db.alerts.find_one({"alert_id": out["alert_id"]},
                                        {"_id": 0, "activation_id": 1})
            out["activation_id"] = raw_event["activation_id"] = (a or {}).get("activation_id")
        await alog("rf", "activation_admitted", room=room, resident_id=resident_id,
                   rf_device_id=rf_device_id, alert_id=out["alert_id"],
                   activation_id=out["activation_id"],
                   data={"semantic_class": rfclass.semantic, "reasons": rfclass.reasons,
                         "press_counted": raw_event.get("press_counted"),
                         "rf_burst_id": raw_event.get("rf_burst_id")})
    except Exception as e:
        log.warning(f"RF help-press activation failed for {rf_device_id}: {e}")
        raw_event["activation_error"] = type(e).__name__
    return out
