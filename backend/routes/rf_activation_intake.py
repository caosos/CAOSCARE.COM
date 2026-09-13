"""Convert matched RF frames into counted bursts without discarding frames.

Room 214's observed repeated frames arrive about 0.52s apart. The 2s idle
boundary groups that measured burst, without delaying its first frame.
It is a burst estimate, NOT proof of distinct human presses less than 2s
apart. Raw captured/received timestamps remain available for qualification.
"""
import uuid
from datetime import timedelta, timezone
from pymongo import ReturnDocument
from deps import db
from models import now_utc
from routes.resident_activation import record_resident_activation

BURST_IDLE_SECONDS = 2


async def record_matched_frame(device, kiosk, payload, raw_event):
    # rtl_433 runs with -M utc. Normalize its sometimes-naive UTC timestamp
    # so a delayed HTTP delivery is grouped by capture time, not latency.
    captured = payload.captured_at or now_utc()
    if captured.tzinfo is None:
        captured = captured.replace(tzinfo=timezone.utc)
    stamp = captured.astimezone(timezone.utc).isoformat()
    cutoff = (captured - timedelta(seconds=BURST_IDLE_SECONDS)).astimezone(timezone.utc).isoformat()
    telemetry = {"last_seen_at": now_utc().isoformat(), "last_rssi": payload.fingerprint.rssi}
    battery_ok = (payload.fingerprint.decoded or {}).get("battery_ok")
    if battery_ok is not None:
        telemetry["low_battery"] = not bool(battery_ok)
    state = await db.rf_devices.find_one_and_update(
        {"rf_device_id": device["rf_device_id"]}, [{"$set": {
            **telemetry,
            "_rf_burst_id": {"$cond": [
                {"$gte": [{"$ifNull": ["$_rf_last_capture", ""]}, cutoff]},
                {"$ifNull": ["$_rf_burst_id", uuid.uuid4().hex]}, uuid.uuid4().hex,
            ]},
            "_rf_last_capture": {"$max": [{"$ifNull": ["$_rf_last_capture", ""]}, stamp]},
            "rf_frame_count": {"$add": [{"$ifNull": ["$rf_frame_count", 0]}, 1]},
        }}], return_document=ReturnDocument.AFTER,
    )
    burst_id = state["_rf_burst_id"]
    raw_event.update(rf_burst_id=burst_id, press_count_basis="rf_burst_2s_idle")
    severity = {"help": "assist", "assist": "assist", "emergency": "emergency", "comfort": "comfort"}.get(device.get("severity"), "assist")
    result = await record_resident_activation(
        resident_id=device.get("resident_id"), room=device.get("room") or kiosk.get("room"),
        source="rf_pendant", device_id=device["rf_device_id"], press_id=burst_id,
        rssi=payload.fingerprint.rssi, severity=severity, auto_voice=True,
        message=f"RF pendant pressed: {device.get('label', 'unknown')}",
        triggered_by="rf_pendant", kiosk_id=payload.kiosk_id,
        source_metadata={"rf_device_id": device["rf_device_id"],
                         "match_score": raw_event["match_score"], "rssi": payload.fingerprint.rssi,
                         "rf_severity": device.get("severity", "help"),
                         "press_count_basis": "rf_burst_2s_idle"},
    )
    counted = not result.get("duplicate_press", False)
    raw_event.update(alert_id=result["alert_id"], press_counted=counted)
    if counted:
        await db.rf_devices.update_one({"rf_device_id": device["rf_device_id"]}, {"$inc": {"press_count": 1}})
    return result["coalesced"]
