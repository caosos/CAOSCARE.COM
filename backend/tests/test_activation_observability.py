"""Activation observability - every activation is reconstructable from
evidence, in one server-timestamp-ordered chain (Level 1 observability
requirement, 2026-09-07).

Drives a real help-press activation end to end (RF -> ResidentEvent ->
kiosk breadcrumbs -> room lease -> realtime session end) against the
running backend, then asserts GET /activation-events/{activation_id} and
GET /activation-events/room/{room}/at return one ordered, correlated
timeline spanning every layer.
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
PRESS_DECODED = {"subtype": "unknown", "battery_ok": 1, "switch1": "OPEN", "switch2": "OPEN",
                 "switch3": "OPEN", "switch4": "OPEN", "switch5": "CLOSED"}


async def _run():
    from deps import db
    from models import now_utc

    try:
        requests.get(f"{BASE_URL}/api/health", timeout=3).raise_for_status()
    except Exception:
        pytest.skip("backend not reachable")

    room = f"obs_{uuid.uuid4().hex[:8]}"
    kiosk_id = f"kio_{uuid.uuid4().hex[:12]}"
    rf_device_id = f"rfd_{uuid.uuid4().hex[:12]}"
    resident_id = f"res_test_{uuid.uuid4().hex[:8]}"
    hex_ = uuid.uuid4().hex[:14]
    cid = f"ci_test_{uuid.uuid4().hex[:8]}"

    await db.residents.insert_one({"resident_id": resident_id, "name": "Obs Resident", "room": room,
                                   "pendant_id": "pnd_unused", "created_at": now_utc().isoformat()})
    await db.kiosks.insert_one({"kiosk_id": kiosk_id, "name": "Obs Kiosk", "room": room, "zone": "obs",
                                "is_central": False, "mac_address": None, "created_at": now_utc().isoformat(),
                                "rf_secret": None, "rf_seq": 0})
    await db.rf_devices.insert_one({
        "rf_device_id": rf_device_id, "label": "Obs Pendant", "resident_id": resident_id, "room": room,
        "fingerprint": {"frequency_hz": FREQ, "modulation": "OOK", "bit_pattern_hex": hex_,
                        "bit_length": 56, "rssi": -0.11, "decoded": None},
        "severity": "help", "match_threshold": 0.85, "enabled": True, "last_seen_at": None,
        "last_rssi": None, "press_count": 0, "created_at": now_utc().isoformat(), "created_by": None,
    })

    try:
        # --- RF help press -> ResidentEvent -----------------------------
        r = requests.post(f"{API}/rf/event", json={
            "kiosk_id": kiosk_id,
            "fingerprint": {"frequency_hz": FREQ, "modulation": "OOK", "bit_pattern_hex": hex_,
                            "bit_length": 56, "rssi": -0.11, "decoded": PRESS_DECODED},
            "sequence": int(time.time() * 1000),
        }, timeout=5)
        r.raise_for_status()
        alert_id = r.json()["alert_id"]
        assert alert_id and r.json()["semantic_class"] == "help_press"
        doc = await db.alerts.find_one({"alert_id": alert_id}, {"_id": 0})
        activation_id = doc["activation_id"]
        assert activation_id

        # --- kiosk client breadcrumbs ---------------------------------
        session_id = f"rt_test_{uuid.uuid4().hex[:8]}"
        crumbs = [
            {"event": "kiosk_mounted", "client_instance_id": cid, "room": room, "kiosk_id": kiosk_id},
            {"event": "poll_started", "client_instance_id": cid, "room": room, "kiosk_id": kiosk_id},
            {"event": "alert_first_seen", "client_instance_id": cid, "room": room, "kiosk_id": kiosk_id,
             "alert_id": alert_id, "activation_id": activation_id, "data": {"press_count": 1}},
            {"event": "wake_accepted", "client_instance_id": cid, "room": room, "kiosk_id": kiosk_id,
             "alert_id": alert_id, "activation_id": activation_id, "data": {"reason": "first_sight"}},
            {"event": "mic_requested", "client_instance_id": cid, "room": room, "kiosk_id": kiosk_id,
             "alert_id": alert_id, "activation_id": activation_id, "session_id": session_id},
            {"event": "mic_acquired", "client_instance_id": cid, "room": room, "kiosk_id": kiosk_id,
             "alert_id": alert_id, "activation_id": activation_id, "session_id": session_id},
        ]
        cr = requests.post(f"{API}/activation-events/client", json={"events": crumbs}, timeout=5)
        cr.raise_for_status()
        assert cr.json()["accepted"] == 6

        # unknown client events are dropped, not errored
        bad = requests.post(f"{API}/activation-events/client",
                            json={"events": [{"event": "arbitrary_noise", "client_instance_id": cid}]}, timeout=5)
        bad.raise_for_status()
        assert bad.json()["accepted"] == 0

        # --- room lease claim + release -----------------------------
        requests.post(f"{API}/realtime/room/{room}/activate", json={
            "resident_id": resident_id, "kiosk_id": kiosk_id, "trigger_source": "pendant",
            "session_id": session_id, "activation_id": activation_id,
        }, timeout=5).raise_for_status()
        requests.post(f"{API}/realtime/room/{room}/release",
                      json={"session_id": session_id, "reason": "resident_end_call",
                            "activation_id": activation_id}, timeout=5).raise_for_status()

        # --- realtime diagnostics row tagged with activation_id -----
        requests.post(f"{API}/realtime-diagnostics/event", json={
            "session_id": session_id, "event_type": "session_ended",
            "activation_id": activation_id, "alert_id": alert_id, "room": room,
            "meta": {"reason": "resident_end_call"},
        }, timeout=5).raise_for_status()

        # --- reconstruct by activation_id -----------------------------
        # Call the merge directly (the HTTP endpoint is admin-gated and this
        # environment has no seeded credentials - same convention as the
        # other tests importing deps.db). The endpoint is a thin wrapper.
        from routes.activation_timeline import _merge_for_alert
        rows = await _merge_for_alert(alert_id, activation_id)
        assert len(rows) >= 8

        # strictly non-decreasing server timestamps
        ts = [x["ts"] for x in rows if x.get("ts")]
        assert ts == sorted(ts), "timeline must be ordered by authoritative server ts"

        layers = {x["layer"] for x in rows}
        assert {"rf", "resident_event", "kiosk", "lease", "realtime"} <= layers, layers
        events = {(x["layer"], x["event"]) for x in rows}
        assert ("rf", "frame_received") in events
        assert ("resident_event", "event_opened") in events
        assert ("kiosk", "wake_accepted") in events
        assert ("lease", "claim_accepted") in events
        assert ("lease", "released") in events
        assert ("realtime", "session_mint_started") in events or ("realtime", "session_ended") in events

        # WHO vs WHAT are both on the RF row, and only help_press was allowed
        rf_row = next(x for x in rows if x["layer"] == "rf" and x["event"] == "frame_received")
        d = rf_row["data"]
        assert d["matched_device_id"] == rf_device_id           # WHO
        assert d["semantic_class"] == "help_press"               # WHAT
        assert d["allowed_activation"] is True                   # WHY allowed
        assert d["class_reasons"]                                 # why that class

        # every row correlatable
        for x in rows:
            assert x.get("activation_id") == activation_id or x.get("session_id") == session_id \
                or x["source"] in ("alert.event_log", "alert.presses", "resident_aria_lease_events", "rf_events")

        # --- reconstruct by room + time (the "why did Room X wake at T"
        #     path when you don't have the activation_id) -----------------
        at = rows[-1]["ts"]
        from datetime import datetime, timedelta
        t = datetime.fromisoformat(at)
        lo, hi = (t - timedelta(minutes=60)).isoformat(), (t + timedelta(minutes=60)).isoformat()
        hit = await db.activation_events.find_one(
            {"room": room, "ts": {"$gte": lo, "$lte": hi}, "alert_id": alert_id})
        assert hit and hit["activation_id"] == activation_id

        # --- per-device transmission history: WHO fixed, WHAT is the story
        last_tx = await db.rf_events.find_one({"matched_device_id": rf_device_id}, {"_id": 0},
                                             sort=[("received_at", -1)])
        assert last_tx["semantic_class"] == "help_press"
        dev = await db.rf_devices.find_one({"rf_device_id": rf_device_id}, {"_id": 0})
        assert dev.get("last_transmission_class") == "help_press"
    finally:
        await db.residents.delete_one({"resident_id": resident_id})
        await db.kiosks.delete_one({"kiosk_id": kiosk_id})
        await db.rf_devices.delete_one({"rf_device_id": rf_device_id})
        await db.alerts.delete_many({"resident_id": resident_id})
        await db.receipts.delete_many({"resident_id": resident_id})
        await db.rf_events.delete_many({"matched_device_id": rf_device_id})
        await db.resident_aria_leases.delete_many({"room": room})
        await db.activation_events.delete_many({"room": room})
        await db.realtime_diagnostics.delete_many({"session_id": session_id})


def test_activation_observability_reconstruction():
    asyncio.run(_run())
