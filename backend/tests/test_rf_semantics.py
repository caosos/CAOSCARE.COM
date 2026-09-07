"""RF transmission-semantics gate (Level 1 directive, 2026-09-07).

WHO transmitted (fingerprint match) is NOT the same question as WHAT they
transmitted. Only a proven `help_press` may enter the resident-assistance
activation path. Supervisory / unknown transmissions from a matched paired
device update health telemetry and are logged, but must not touch the
ResidentEvent, the room lease, or Aria.

Uses the REAL captured Room 214 Lifeline signatures as fixtures:
  supervisory : all decoded switches OPEN, short 3-frame burst, ~64 min cadence
  help_press  : decoded switch5 CLOSED (switch1-4 OPEN), 8+ frame burst

Hits the real running backend over HTTP with synthetic isolated fixtures
(never touches real resident data). Skips cleanly if unreachable.
Run: pytest tests/test_rf_semantics.py -q
"""
import asyncio
import os
import sys
import time
import uuid

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "http://127.0.0.1:8000").rstrip("/")
API = f"{BASE_URL}/api"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

FREQ = 319_500_000
# WHO: a UNIQUE synthetic identity per fixture (never the real paired
# pendant's hash - reusing that would match rfd_6e8f06632b41 and mutate real
# device telemetry). WHAT: the REAL captured Room 214 decoded semantic
# signatures below (switch5 OPEN vs CLOSED; 3-frame vs 8-frame burst).
SUPERVISORY_DECODED = {"subtype": "unknown", "battery_ok": 1,
                       "switch1": "OPEN", "switch2": "OPEN", "switch3": "OPEN",
                       "switch4": "OPEN", "switch5": "OPEN"}
HELP_PRESS_DECODED = {"subtype": "unknown", "battery_ok": 1,
                      "switch1": "OPEN", "switch2": "OPEN", "switch3": "OPEN",
                      "switch4": "OPEN", "switch5": "CLOSED"}
UNKNOWN_DECODED = {"subtype": "unknown", "battery_ok": 1,
                   "switch1": "CLOSED", "switch2": "OPEN", "switch3": "CLOSED",
                   "switch4": "OPEN", "switch5": "OPEN"}

_SEQ = [int(time.time()) * 1000]
_HEX = [None]  # set by _fixture; the current fixture's unique identity


def _frame(kiosk_id, decoded, hex_=None, rssi=-0.11):
    _SEQ[0] += 1
    r = requests.post(f"{API}/rf/event", json={
        "kiosk_id": kiosk_id,
        "fingerprint": {"frequency_hz": FREQ, "modulation": "OOK",
                        "bit_pattern_hex": hex_ or _HEX[0],
                        "bit_length": 56, "rssi": rssi, "decoded": decoded},
        "sequence": _SEQ[0],
    }, timeout=5)
    r.raise_for_status()
    return r.json()


def _burst(kiosk_id, decoded, n, gap=0.15, hex_=None):
    out = []
    for i in range(n):
        if i:
            time.sleep(gap)
        out.append(_frame(kiosk_id, decoded, hex_=hex_))
    return out


async def _fixture(db, now_utc, *, threshold=0.85):
    room = f"rfsem_{uuid.uuid4().hex[:8]}"
    kiosk_id = f"kio_{uuid.uuid4().hex[:12]}"
    rf_device_id = f"rfd_{uuid.uuid4().hex[:12]}"
    resident_id = f"res_test_{uuid.uuid4().hex[:8]}"
    _HEX[0] = uuid.uuid4().hex[:14]  # unique synthetic identity, never the real hash
    await db.residents.insert_one({"resident_id": resident_id, "name": "Semantics Resident",
                                   "room": room, "pendant_id": "pnd_unused",
                                   "created_at": now_utc().isoformat()})
    await db.kiosks.insert_one({"kiosk_id": kiosk_id, "name": "RF Sem Kiosk", "room": room,
                                "zone": "semtest", "is_central": False, "mac_address": None,
                                "created_at": now_utc().isoformat(), "rf_secret": None, "rf_seq": 0})
    await db.rf_devices.insert_one({
        "rf_device_id": rf_device_id, "label": "RF Sem Pendant", "resident_id": resident_id,
        "room": room,
        "fingerprint": {"frequency_hz": FREQ, "modulation": "OOK",
                        "bit_pattern_hex": _HEX[0], "bit_length": 56, "rssi": -0.11,
                        "decoded": None},
        "severity": "help", "match_threshold": threshold, "enabled": True,
        "last_seen_at": None, "last_rssi": None, "press_count": 0,
        "created_at": now_utc().isoformat(), "created_by": None,
    })
    return room, kiosk_id, rf_device_id, resident_id


async def _cleanup(db, room, kiosk_id, rf_device_id, resident_id):
    await db.residents.delete_one({"resident_id": resident_id})
    await db.kiosks.delete_one({"kiosk_id": kiosk_id})
    await db.rf_devices.delete_one({"rf_device_id": rf_device_id})
    await db.alerts.delete_many({"resident_id": resident_id})
    await db.receipts.delete_many({"resident_id": resident_id})
    await db.rf_events.delete_many({"matched_device_id": rf_device_id})
    await db.rf_events.delete_many({"fingerprint.bit_pattern_hex": _HEX[0], "matched_device_id": None})
    await db.resident_aria_leases.delete_many({"room": room})
    await db.activation_events.delete_many({"room": room})


async def _run_all():
    from deps import db
    from models import now_utc

    try:
        requests.get(f"{BASE_URL}/api/health", timeout=3).raise_for_status()
    except Exception:
        pytest.skip("backend not reachable")

    await _t1_supervisory_no_activation(db, now_utc)
    await _t2_deliberate_press(db, now_utc)
    await _t3_unknown_message(db, now_utc)
    await _t4_multi_frame_one_press(db, now_utc)
    await _t5_supervisory_while_event_open(db, now_utc)
    await _t6_supervisory_keeps_health_current(db, now_utc)


# 1. Proven supervisory: matched, health updated, class=supervisory,
#    zero ResidentEvent mutation, zero human press, zero Aria activation.
async def _t1_supervisory_no_activation(db, now_utc):
    room, kiosk_id, rf_device_id, resident_id = await _fixture(db, now_utc)
    try:
        before_alerts = await db.alerts.count_documents({"resident_id": resident_id})
        res = _burst(kiosk_id, SUPERVISORY_DECODED, 3)
        for r in res:
            assert r["matched"] is True
            assert r["semantic_class"] == "supervisory"
            assert r["allowed_activation"] is False
            assert r["alert_id"] is None
        assert await db.alerts.count_documents({"resident_id": resident_id}) == before_alerts
        dev = await db.rf_devices.find_one({"rf_device_id": rf_device_id}, {"_id": 0})
        assert dev["last_seen_at"] is not None
        assert dev.get("press_count", 0) == 0, "supervisory must not increment human press_count"
        assert dev.get("supervisory_count", 0) >= 1
        assert dev.get("last_transmission_class") == "supervisory"
        assert await db.resident_aria_leases.count_documents({"room": room}) == 0
        rfe = await db.rf_events.find_one({"matched_device_id": rf_device_id}, {"_id": 0}, sort=[("received_at", -1)])
        assert rfe["semantic_class"] == "supervisory" and rfe["allowed_activation"] is False
        assert "all_switches_open" in rfe["class_reasons"]
        cls = await db.activation_events.count_documents({"room": room, "layer": "rf", "event": "frame_classified"})
        sup = await db.activation_events.count_documents({"room": room, "layer": "rf", "event": "activation_suppressed"})
        assert cls >= 3 and sup >= 3, "every classified supervisory frame must be traceable"
    finally:
        await _cleanup(db, room, kiosk_id, rf_device_id, resident_id)


# 2. Proven deliberate press: class=help_press, one human press, normal
#    ResidentEvent activation.
async def _t2_deliberate_press(db, now_utc):
    room, kiosk_id, rf_device_id, resident_id = await _fixture(db, now_utc)
    try:
        first = _frame(kiosk_id, HELP_PRESS_DECODED)
        assert first["semantic_class"] == "help_press"
        assert first["allowed_activation"] is True
        alert_id = first["alert_id"]
        assert alert_id
        doc = await db.alerts.find_one({"alert_id": alert_id}, {"_id": 0})
        assert doc["press_count"] == 1
        assert doc.get("activation_id")
        assert len(doc["presses"]) == 1
        rfe = await db.rf_events.find_one({"alert_id": alert_id}, {"_id": 0})
        assert rfe["semantic_class"] == "help_press" and rfe["allowed_activation"] is True
        assert "decoded_press_signature_switch5_closed" in rfe["class_reasons"]
        opened = await db.activation_events.count_documents(
            {"room": room, "layer": "resident_event", "event": "event_opened"})
        assert opened == 1
    finally:
        await _cleanup(db, room, kiosk_id, rf_device_id, resident_id)


# 3. Unknown matched message: class=unknown, raw evidence retained, no
#    assistance activation.
async def _t3_unknown_message(db, now_utc):
    room, kiosk_id, rf_device_id, resident_id = await _fixture(db, now_utc)
    try:
        before_alerts = await db.alerts.count_documents({"resident_id": resident_id})
        r = _frame(kiosk_id, UNKNOWN_DECODED)
        assert r["matched"] is True
        assert r["semantic_class"] == "unknown"
        assert r["allowed_activation"] is False
        assert r["alert_id"] is None
        assert await db.alerts.count_documents({"resident_id": resident_id}) == before_alerts
        rfe = await db.rf_events.find_one({"matched_device_id": rf_device_id}, {"_id": 0}, sort=[("received_at", -1)])
        assert rfe is not None, "raw RF evidence must be retained for an unknown message"
        assert rfe["semantic_class"] == "unknown"
        assert rfe["fingerprint"]["decoded"]["switch1"] == "CLOSED"
        dev = await db.rf_devices.find_one({"rf_device_id": rf_device_id}, {"_id": 0})
        assert dev.get("unknown_count", 0) >= 1
        assert dev.get("press_count", 0) == 0
    finally:
        await _cleanup(db, room, kiosk_id, rf_device_id, resident_id)


# 4. Multiple frames from ONE help press: still exactly one human press
#    after burst/debounce handling.
async def _t4_multi_frame_one_press(db, now_utc):
    room, kiosk_id, rf_device_id, resident_id = await _fixture(db, now_utc)
    try:
        res = _burst(kiosk_id, HELP_PRESS_DECODED, 8, gap=0.12)
        for r in res:
            assert r["semantic_class"] == "help_press"
        alert_id = res[0]["alert_id"]
        assert alert_id and all(r["alert_id"] == alert_id for r in res)
        doc = await db.alerts.find_one({"alert_id": alert_id}, {"_id": 0})
        assert doc["press_count"] == 1, "8 frames of one physical press = one human press"
        assert len(doc["presses"]) == 1
        dev = await db.rf_devices.find_one({"rf_device_id": rf_device_id}, {"_id": 0})
        assert dev.get("press_count", 0) == 1, "device human press tally counts the press once, not per frame"
        # every raw frame kept
        assert await db.rf_events.count_documents({"matched_device_id": rf_device_id}) == 8
    finally:
        await _cleanup(db, room, kiosk_id, rf_device_id, resident_id)


# 5. Supervisory frame while an OLD ResidentEvent is open (dismissed but not
#    staff-resolved): must NOT re-arm it, NOT reset activation_consumed_at,
#    NOT wake Aria.
async def _t5_supervisory_while_event_open(db, now_utc):
    room, kiosk_id, rf_device_id, resident_id = await _fixture(db, now_utc)
    try:
        press = _frame(kiosk_id, HELP_PRESS_DECODED)
        alert_id = press["alert_id"]
        # simulate a session that ran and was dismissed (consumes activation)
        requests.post(f"{API}/alerts/{alert_id}/aria-event", json={"event": "dismissed"}, timeout=5).raise_for_status()
        pre = await db.alerts.find_one({"alert_id": alert_id}, {"_id": 0})
        assert pre["activation_consumed_at"] is not None
        pc_before, consumed_before, aid_before = pre["press_count"], pre["activation_consumed_at"], pre["activation_id"]

        time.sleep(3.4)  # clear the RF echo window so this isn't just an echo frame
        for r in _burst(kiosk_id, SUPERVISORY_DECODED, 3):
            assert r["semantic_class"] == "supervisory"
            assert r["allowed_activation"] is False
            assert r["alert_id"] is None

        post = await db.alerts.find_one({"alert_id": alert_id}, {"_id": 0})
        assert post["press_count"] == pc_before, "supervisory must not increment press_count on an open event"
        assert post["activation_consumed_at"] == consumed_before, "supervisory must NOT reset activation_consumed_at"
        assert post["activation_id"] == aid_before, "supervisory must NOT start a new activation cycle"
        assert await db.resident_aria_leases.count_documents({"room": room}) == 0, "supervisory must not claim a room lease"
        # active-emergency stays suppressed (consumed), so no Aria relaunch
        ae = requests.get(f"{API}/kiosks/{kiosk_id}/active-emergency", timeout=5).json()
        assert ae["alert"] is None, "a dismissed event must not resurface for Aria off a supervisory frame"
    finally:
        await _cleanup(db, room, kiosk_id, rf_device_id, resident_id)


# 6. Supervisory transmission must still keep pendant-health telemetry current.
async def _t6_supervisory_keeps_health_current(db, now_utc):
    room, kiosk_id, rf_device_id, resident_id = await _fixture(db, now_utc)
    try:
        await db.rf_devices.update_one({"rf_device_id": rf_device_id},
                                       {"$set": {"last_seen_at": "2000-01-01T00:00:00+00:00",
                                                 "last_rssi": None}})
        _burst(kiosk_id, {**SUPERVISORY_DECODED, "battery_ok": 0}, 3, hex_=_HEX[0])
        dev = await db.rf_devices.find_one({"rf_device_id": rf_device_id}, {"_id": 0})
        assert dev["last_seen_at"] > "2020-01-01", "supervisory must refresh last_seen_at"
        assert dev["last_rssi"] is not None, "supervisory must refresh RSSI"
        assert dev.get("last_transmission_at") is not None
        assert dev.get("last_transmission_class") in ("supervisory", "battery_status")
        assert dev.get("low_battery") is True, "supervisory must propagate battery health"
    finally:
        await _cleanup(db, room, kiosk_id, rf_device_id, resident_id)


def test_rf_transmission_semantics():
    asyncio.run(_run_all())
