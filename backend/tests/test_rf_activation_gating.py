"""Regression test for the RF pendant repeat-activation defect
(docs/PROJECT_STATE.md, 2026-08-30, room 401 live acceptance test).

Reproduces Michael's exact acceptance-test steps against a synthetic,
isolated kiosk/room/RF device so it never touches real resident alert
history. Hits the real running backend over HTTP (/rf/event, active-
emergency, room lease activate/release) - the same public endpoints the
bridge daemon and kiosk actually call - for the behavior under test.
Setup/teardown of the synthetic fixtures use direct Mongo access, same
convention as test_room_device_isolation.py's `admin` fixture.

Everything - setup, HTTP calls, DB verification, teardown - runs inside
ONE asyncio.run() call. Motor's AsyncIOMotorClient binds to the event loop
of whichever asyncio.run() call touches it first; a second, separate
asyncio.run() in the same process gets a fresh loop and raises "Event loop
is closed" against that cached client. `requests` calls are synchronous
and safe to make from inside an async function regardless.

Requires the local backend running (REACT_APP_BACKEND_URL, defaults to
http://127.0.0.1:8000). Skips cleanly if unreachable.

Run with: pytest tests/test_rf_activation_gating.py -q
"""
import asyncio
import os
import sys
import uuid

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "http://127.0.0.1:8000").rstrip("/")
API = f"{BASE_URL}/api"

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

FREQ = 319_500_000
FP_HEX = "aabbccdd11"  # fixed synthetic fingerprint - exact match, hamming score 1.0


def _press(kiosk_id, seq):
    r = requests.post(f"{API}/rf/event", json={
        "kiosk_id": kiosk_id,
        "fingerprint": {"frequency_hz": FREQ, "modulation": "OOK", "bit_pattern_hex": FP_HEX,
                         "bit_length": 40, "rssi": -50},
        "sequence": seq,
    }, timeout=5)
    r.raise_for_status()
    return r.json()


def _active_emergency(kiosk_id):
    r = requests.get(f"{API}/kiosks/{kiosk_id}/active-emergency", timeout=5)
    r.raise_for_status()
    return r.json()


async def _run_acceptance_sequence():
    from deps import db
    from models import now_utc

    try:
        requests.get(f"{BASE_URL}/api/health", timeout=3).raise_for_status()
    except Exception:
        pytest.skip("backend not reachable")

    room = f"rftest_{uuid.uuid4().hex[:8]}"
    kiosk_id = f"kio_{uuid.uuid4().hex[:12]}"
    rf_device_id = f"rfd_{uuid.uuid4().hex[:12]}"

    await db.kiosks.insert_one({
        "kiosk_id": kiosk_id, "name": "RF Test Kiosk", "room": room, "zone": "test",
        "is_central": False, "mac_address": None, "created_at": now_utc().isoformat(),
        "rf_secret": None, "rf_seq": 0,
    })
    await db.rf_devices.insert_one({
        "rf_device_id": rf_device_id, "label": "RF Test Pendant", "resident_id": None,
        "room": room,
        "fingerprint": {"frequency_hz": FREQ, "modulation": "OOK", "bit_pattern_hex": FP_HEX,
                         "bit_length": 40, "rssi": -50, "decoded": None},
        "severity": "help", "match_threshold": 0.85, "enabled": True,
        "last_seen_at": None, "last_rssi": None, "press_count": 0,
        "created_at": now_utc().isoformat(), "created_by": None,
    })

    try:
        # Step 1-2: both idle, press pendant once -> exactly one activation.
        assert _active_emergency(kiosk_id)["alert"] is None
        r1 = _press(kiosk_id, 1)
        assert r1.get("press_coalesced") is not True
        alert_a = r1["alert_id"]
        assert alert_a
        seen = _active_emergency(kiosk_id)["alert"]
        assert seen and seen["alert_id"] == alert_a

        # Step 3: press pendant 5 more times while "Aria is active".
        for seq in range(2, 7):
            r = _press(kiosk_id, seq)
            assert r["press_coalesced"] is True, f"press {seq} should coalesce into the open incident"
            assert r["alert_id"] == alert_a, "no new alert should be minted while the incident is open"
        still_seen = _active_emergency(kiosk_id)["alert"]
        assert still_seen and still_seen["alert_id"] == alert_a, "still exactly one active incident"

        # Step 4: end that session (claim + release the room lease,
        # mirroring what a real Resident Aria session does on connect/
        # disconnect - see useRealtimeVoice.js's stop()).
        session_id = f"rt_test_{uuid.uuid4().hex[:8]}"
        activate = requests.post(f"{API}/realtime/room/{room}/activate", json={
            "resident_id": None, "kiosk_id": kiosk_id, "trigger_source": "pendant", "session_id": session_id,
        }, timeout=5).json()
        assert activate["claimed"] is True
        rel = requests.post(f"{API}/realtime/room/{room}/release", json={"session_id": session_id}, timeout=5).json()
        assert rel["ok"] is True

        # Step 4-5: both clients idle, no deferred/backlogged session, even
        # though alert_a's status is still "active" (staff-facing, untouched).
        after_close = _active_emergency(kiosk_id)["alert"]
        assert after_close is None, "a consumed incident must not resurface and auto-launch a new session"

        # Step 6-7: a genuinely NEW press after close creates a fresh
        # incident, and the old one can never reactivate.
        r_new = _press(kiosk_id, 7)
        assert r_new.get("press_coalesced") is not True
        alert_b = r_new["alert_id"]
        assert alert_b and alert_b != alert_a, "a post-close press must create a NEW activation, not reuse the old one"
        fresh = _active_emergency(kiosk_id)["alert"]
        assert fresh and fresh["alert_id"] == alert_b

        # Repeat presses 1-6 are intact evidence on the OLD, now-consumed
        # incident - never smuggled onto the new one.
        alert_a_doc = await db.alerts.find_one({"alert_id": alert_a}, {"_id": 0})
        assert alert_a_doc["press_count"] == 6
        assert alert_a_doc["activation_consumed_at"] is not None
        alert_b_doc = await db.alerts.find_one({"alert_id": alert_b}, {"_id": 0})
        assert alert_b_doc["press_count"] == 1
        assert alert_b_doc["activation_consumed_at"] is None
    finally:
        await db.kiosks.delete_one({"kiosk_id": kiosk_id})
        await db.rf_devices.delete_one({"rf_device_id": rf_device_id})
        await db.alerts.delete_many({"room": room})
        await db.rf_events.delete_many({"fingerprint.bit_pattern_hex": FP_HEX})
        await db.resident_aria_leases.delete_many({"room": room})


def test_acceptance_sequence():
    """Mirrors Michael's live two-browser acceptance test step by step."""
    asyncio.run(_run_acceptance_sequence())
