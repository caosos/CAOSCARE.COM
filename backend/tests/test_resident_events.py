"""Regression tests for the Level 1 resident-assistance event model
(docs/PROJECT_STATE.md, 2026-09-06 directive).

Supersedes the old test_rf_activation_gating.py, whose own assertions
encoded the PRIOR (now intentionally changed) behavior: a post-dismissal
repeat press used to mint a brand new alert. That was the exact defect
Michael's directive corrected - a still-open (unresolved) event must
reactivate Aria on THE SAME alert_id, not a new one. Steps 1-3 here are
the same acceptance sequence; steps 4+ assert the corrected behavior.

Hits the real running backend over HTTP (/rf/event, /alerts, active-
emergency, room lease activate/release, staff-present) using synthetic,
isolated fixtures so it never touches real resident data - same
convention as the file it replaces. Requires the local backend running
(REACT_APP_BACKEND_URL, defaults to http://127.0.0.1:8000). Skips cleanly
if unreachable.

Run with: pytest tests/test_resident_events.py -q
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
FP_HEX = "aabbccdd11"

# How long the test must wait for the backend's RF echo window to close
# before a press counts as a genuinely separate physical press. Mirrors
# routes/resident_activation.RF_PRESS_DEBOUNCE_SECONDS; a test backend can
# export RF_PRESS_DEBOUNCE_SECONDS low to keep this fast.
try:
    _DEBOUNCE = float(os.environ.get("RF_PRESS_DEBOUNCE_SECONDS", "4"))
except ValueError:
    _DEBOUNCE = 4.0
PAST_ECHO_WINDOW = _DEBOUNCE + 0.6


def _press(kiosk_id, seq, fp_hex=FP_HEX):
    r = requests.post(f"{API}/rf/event", json={
        "kiosk_id": kiosk_id,
        "fingerprint": {"frequency_hz": FREQ, "modulation": "OOK", "bit_pattern_hex": fp_hex,
                         "bit_length": 40, "rssi": -50},
        "sequence": seq,
    }, timeout=5)
    r.raise_for_status()
    return r.json()


def _active_emergency(kiosk_id):
    r = requests.get(f"{API}/kiosks/{kiosk_id}/active-emergency", timeout=5)
    r.raise_for_status()
    return r.json()


async def _run_reactivation_sequence():
    from deps import db
    from models import now_utc

    try:
        requests.get(f"{BASE_URL}/api/health", timeout=3).raise_for_status()
    except Exception:
        pytest.skip("backend not reachable")

    room = f"rftest_{uuid.uuid4().hex[:8]}"
    kiosk_id = f"kio_{uuid.uuid4().hex[:12]}"
    rf_device_id = f"rfd_{uuid.uuid4().hex[:12]}"
    resident_id = f"res_test_{uuid.uuid4().hex[:8]}"

    await db.residents.insert_one({
        "resident_id": resident_id, "name": "Test Resident", "room": room,
        "pendant_id": "pnd_unused", "created_at": now_utc().isoformat(),
    })
    await db.kiosks.insert_one({
        "kiosk_id": kiosk_id, "name": "RF Test Kiosk", "room": room, "zone": "test",
        "is_central": False, "mac_address": None, "created_at": now_utc().isoformat(),
        "rf_secret": None, "rf_seq": 0,
    })
    await db.rf_devices.insert_one({
        "rf_device_id": rf_device_id, "label": "RF Test Pendant", "resident_id": resident_id,
        "room": room,
        "fingerprint": {"frequency_hz": FREQ, "modulation": "OOK", "bit_pattern_hex": FP_HEX,
                         "bit_length": 40, "rssi": -50, "decoded": None},
        "severity": "help", "match_threshold": 0.85, "enabled": True,
        "last_seen_at": None, "last_rssi": None, "press_count": 0,
        "created_at": now_utc().isoformat(), "created_by": None,
    })

    try:
        # 1-2: one press opens exactly one event.
        assert _active_emergency(kiosk_id)["alert"] is None
        r1 = _press(kiosk_id, 1)
        assert r1.get("press_coalesced") is not True
        alert_a = r1["alert_id"]
        assert alert_a
        seen = _active_emergency(kiosk_id)["alert"]
        assert seen and seen["alert_id"] == alert_a

        # 3: rapid repeat FRAMES of the same physical press are RF echo -
        # they must NOT inflate press_count / presses[] (break-test
        # invariants 2, 3). Sent back-to-back with no delay, exactly as the
        # android bridge POSTs one pendant press's ~3-8 frames.
        for seq in range(2, 6):
            r = _press(kiosk_id, seq)
            assert r["alert_id"] == alert_a
            assert r.get("echo_frame") is True, "a same-press repeat frame must be classified as echo"
        doc = await db.alerts.find_one({"alert_id": alert_a}, {"_id": 0})
        assert doc["press_count"] == 1, "RF echo frames must not inflate press_count"
        assert len(doc["presses"]) == 1, "RF echo frames must not be recorded as separate human presses"

        # 3b: a genuine SECOND physical press AFTER the echo window is a real,
        # separate increment (invariant 4 - real repeat presses preserved).
        time.sleep(PAST_ECHO_WINDOW)
        r = _press(kiosk_id, 6)
        assert r["alert_id"] == alert_a
        assert r["press_coalesced"] is True
        assert r.get("echo_frame") is not True
        doc = await db.alerts.find_one({"alert_id": alert_a}, {"_id": 0})
        assert doc["press_count"] == 2
        assert len(doc["presses"]) == 2, "every real press must be preserved as its own record"

        # 4: end the session (claim + release the room lease).
        session_id = f"rt_test_{uuid.uuid4().hex[:8]}"
        activate = requests.post(f"{API}/realtime/room/{room}/activate", json={
            "resident_id": resident_id, "kiosk_id": kiosk_id, "trigger_source": "pendant", "session_id": session_id,
        }, timeout=5).json()
        assert activate["claimed"] is True

        # 2026-09-06 (decouple ResidentEvent lifetime from Realtime session
        # lifetime): a PLAIN lease release - no explicit dismissal/timeout
        # posted first - simulates a connection that just DIED (network
        # drop, ICE failure, a moved endpoint, an in-flight auto-reconnect).
        # release() must NOT consume the activation on its own, since it
        # has no way to tell "resident said goodbye" apart from "the
        # connection died" - the event must stay immediately relaunchable.
        rel = requests.post(f"{API}/realtime/room/{room}/release", json={"session_id": session_id}, timeout=5).json()
        assert rel["ok"] is True
        still_hot = _active_emergency(kiosk_id)["alert"]
        assert still_hot and still_hot["alert_id"] == alert_a, "a session that just DIED must not suppress relaunch - no fresh press required"

        # A different endpoint/session_id can immediately claim the same
        # room and continue serving the same event - auto-recovery /
        # moved-endpoint invariant, not gated on the prior session at all.
        recovery_session = f"rt_recovered_{uuid.uuid4().hex[:8]}"
        recover = requests.post(f"{API}/realtime/room/{room}/activate", json={
            "resident_id": resident_id, "kiosk_id": kiosk_id, "trigger_source": "pendant", "session_id": recovery_session,
        }, timeout=5).json()
        assert recover["claimed"] is True, "a new endpoint must be able to take ownership after the old session died"

        # NOW the resident actually says goodbye (or the 300s companion
        # timeout fires) - this is the one thing that's allowed to
        # consume the activation, via the explicit aria-event, not via
        # releasing the lease.
        aria_event_r = requests.post(f"{API}/alerts/{alert_a}/aria-event", json={"event": "dismissed"}, timeout=5)
        aria_event_r.raise_for_status()
        assert aria_event_r.json()["aria_state"] == "dismissed"
        requests.post(f"{API}/realtime/room/{room}/release", json={"session_id": recovery_session}, timeout=5)
        assert _active_emergency(kiosk_id)["alert"] is None, "an EXPLICIT dismissal must suppress relaunch until a new press"

        # 7: a press AFTER a genuine dismissal, while the event is still
        # open (status active, not resolved by staff), reactivates the
        # SAME event rather than minting a new one. Past the echo window,
        # since a reactivation press is by definition a fresh physical press.
        time.sleep(PAST_ECHO_WINDOW)
        r6 = _press(kiosk_id, 7)
        assert r6["press_coalesced"] is True
        assert r6.get("echo_frame") is not True
        assert r6["alert_id"] == alert_a, "a repeat press on a still-open event must reuse the same alert_id"
        reactivated = _active_emergency(kiosk_id)["alert"]
        assert reactivated and reactivated["alert_id"] == alert_a, "reactivation must relaunch Aria on the SAME event"

        doc = await db.alerts.find_one({"alert_id": alert_a}, {"_id": 0})
        assert doc["press_count"] == 3
        assert doc["activation_consumed_at"] is None

        # Only staff resolving the event actually closes it - simulate that,
        # then prove the NEXT press genuinely opens a fresh event.
        requests.post(f"{API}/realtime/room/{room}/activate", json={
            "resident_id": resident_id, "kiosk_id": kiosk_id, "trigger_source": "pendant",
        }, timeout=5)
        await db.alerts.update_one({"alert_id": alert_a}, {"$set": {"status": "resolved", "resolved_at": now_utc().isoformat()}})

        time.sleep(PAST_ECHO_WINDOW)
        r7 = _press(kiosk_id, 8)
        assert r7["alert_id"] != alert_a, "a press after the event is actually resolved must open a NEW event"
        assert r7.get("echo_frame") is not True
    finally:
        await db.residents.delete_one({"resident_id": resident_id})
        await db.kiosks.delete_one({"kiosk_id": kiosk_id})
        await db.rf_devices.delete_one({"rf_device_id": rf_device_id})
        await db.alerts.delete_many({"resident_id": resident_id})
        await db.receipts.delete_many({"resident_id": resident_id})
        await db.rf_events.delete_many({"fingerprint.bit_pattern_hex": FP_HEX})
        await db.resident_aria_leases.delete_many({"room": room})




async def _run_two_sources_one_event():
    """Acceptance test 16: a second, DIFFERENT mapped device (here: the
    kiosk CALL FOR HELP button) firing while an RF-triggered event is open
    for the same resident must attach to the SAME event, not open a
    second one - the directive's core correction (resident-scoped, not
    resident+device scoped)."""
    from deps import db
    from models import now_utc

    try:
        requests.get(f"{BASE_URL}/api/health", timeout=3).raise_for_status()
    except Exception:
        pytest.skip("backend not reachable")

    room = f"rftest_{uuid.uuid4().hex[:8]}"
    kiosk_id = f"kio_{uuid.uuid4().hex[:12]}"
    rf_device_id = f"rfd_{uuid.uuid4().hex[:12]}"
    resident_id = f"res_test_{uuid.uuid4().hex[:8]}"
    fp_hex = uuid.uuid4().hex[:10]

    await db.residents.insert_one({
        "resident_id": resident_id, "name": "Two Source Resident", "room": room,
        "pendant_id": "pnd_unused", "created_at": now_utc().isoformat(),
    })
    await db.kiosks.insert_one({
        "kiosk_id": kiosk_id, "name": "RF Test Kiosk 2", "room": room, "zone": "test2",
        "is_central": False, "mac_address": None, "created_at": now_utc().isoformat(),
        "rf_secret": None, "rf_seq": 0,
    })
    await db.rf_devices.insert_one({
        "rf_device_id": rf_device_id, "label": "RF Test Pendant 2", "resident_id": resident_id,
        "room": room,
        "fingerprint": {"frequency_hz": FREQ, "modulation": "OOK", "bit_pattern_hex": fp_hex,
                         "bit_length": 40, "rssi": -50, "decoded": None},
        "severity": "help", "match_threshold": 0.85, "enabled": True,
        "last_seen_at": None, "last_rssi": None, "press_count": 0,
        "created_at": now_utc().isoformat(), "created_by": None,
    })

    try:
        r1 = _press(kiosk_id, 101, fp_hex=fp_hex)
        alert_a = r1["alert_id"]
        assert alert_a

        r2 = requests.post(f"{API}/alerts", json={
            "kiosk_id": kiosk_id, "resident_id": resident_id, "severity": "assist",
            "message": "CALL FOR HELP", "triggered_by": "kiosk_button",
        }, timeout=5)
        r2.raise_for_status()
        alert_b = r2.json()["alert_id"]
        assert alert_b == alert_a, "a second mapped source for the same resident must attach to the SAME open event"

        doc = await db.alerts.find_one({"alert_id": alert_a}, {"_id": 0})
        assert doc["press_count"] == 2
        assert len(doc["presses"]) == 2
        sources = {p["source"] for p in doc["presses"]}
        assert sources == {"rf_pendant", "kiosk_button"}
    finally:
        await db.residents.delete_one({"resident_id": resident_id})
        await db.kiosks.delete_one({"kiosk_id": kiosk_id})
        await db.rf_devices.delete_one({"rf_device_id": rf_device_id})
        await db.alerts.delete_many({"resident_id": resident_id})
        await db.receipts.delete_many({"resident_id": resident_id})
        await db.rf_events.delete_many({"fingerprint.bit_pattern_hex": fp_hex})




async def _run_staff_presence_mute():
    from deps import db
    from models import now_utc

    try:
        requests.get(f"{BASE_URL}/api/health", timeout=3).raise_for_status()
    except Exception:
        pytest.skip("backend not reachable")

    room = f"rftest_{uuid.uuid4().hex[:8]}"
    resident_id = f"res_test_{uuid.uuid4().hex[:8]}"
    alert_id = f"alert_test_{uuid.uuid4().hex[:8]}"
    session_id = f"rt_test_{uuid.uuid4().hex[:8]}"

    await db.alerts.insert_one({
        "alert_id": alert_id, "resident_id": resident_id, "room": room,
        "status": "active", "severity": "assist", "aria_state": "active",
        "live_line_state": "ringing", "press_count": 1, "presses": [], "event_log": [],
        "created_at": now_utc().isoformat(), "acknowledged_at": None, "resolved_at": None,
        "activation_consumed_at": None,
    })
    await db.resident_aria_leases.insert_one({
        "room": room, "resident_id": resident_id, "kiosk_id": None, "session_id": session_id,
        "status": "active", "trigger_source": "pendant",
        "created_at": now_utc().isoformat(), "last_seen_at": now_utc().isoformat(),
    })

    try:
        r = requests.post(f"{API}/realtime/room/{room}/staff-present", timeout=5)
        r.raise_for_status()
        body = r.json()
        assert body["ok"] is True
        assert body["lease_dropped"] is True

        doc = await db.alerts.find_one({"alert_id": alert_id}, {"_id": 0})
        assert doc["aria_state"] == "muted_staff"
        assert doc["live_line_state"] == "none"

        lease = await db.resident_aria_leases.find_one({"room": room}, {"_id": 0})
        assert lease is None, "staff presence must immediately drop the room's Aria lease/session"
    finally:
        await db.alerts.delete_one({"alert_id": alert_id})
        await db.resident_aria_leases.delete_many({"room": room})




async def _run_pattern_minimum_history():
    """Patterns must never gate/suppress an activation, and must say "not
    enough history" (i.e. produce no footnote) below pattern_min_events."""
    from deps import db

    try:
        requests.get(f"{BASE_URL}/api/health", timeout=3).raise_for_status()
    except Exception:
        pytest.skip("backend not reachable")

    resident_id = f"res_test_{uuid.uuid4().hex[:8]}"
    from routes.resident_patterns import footnote_for_resident_now

    try:
        footnote = await footnote_for_resident_now(resident_id)
        assert footnote is None, "a resident with zero history must get no footnote, not a fabricated one"
    finally:
        await db.resident_button_patterns.delete_many({"resident_id": resident_id})


async def _run_rf_echo_debounce():
    """Break-test invariants 2, 3, 4: the ~3-8 RF frames one physical pendant
    press emits (android bridge POSTs each frame separately) must collapse to
    ONE press_count increment / ONE presses[] record; frames after the echo
    window are genuine separate presses and each count. Evidence (every raw
    frame) is still written to db.rf_events regardless."""
    from deps import db
    from models import now_utc

    try:
        requests.get(f"{BASE_URL}/api/health", timeout=3).raise_for_status()
    except Exception:
        pytest.skip("backend not reachable")

    room = f"rftest_{uuid.uuid4().hex[:8]}"
    kiosk_id = f"kio_{uuid.uuid4().hex[:12]}"
    rf_device_id = f"rfd_{uuid.uuid4().hex[:12]}"
    resident_id = f"res_test_{uuid.uuid4().hex[:8]}"
    fp_hex = uuid.uuid4().hex[:10]

    await db.residents.insert_one({
        "resident_id": resident_id, "name": "Echo Test Resident", "room": room,
        "pendant_id": "pnd_unused", "created_at": now_utc().isoformat(),
    })
    await db.kiosks.insert_one({
        "kiosk_id": kiosk_id, "name": "RF Echo Kiosk", "room": room, "zone": "echotest",
        "is_central": False, "mac_address": None, "created_at": now_utc().isoformat(),
        "rf_secret": None, "rf_seq": 0,
    })
    await db.rf_devices.insert_one({
        "rf_device_id": rf_device_id, "label": "RF Echo Pendant", "resident_id": resident_id,
        "room": room,
        "fingerprint": {"frequency_hz": FREQ, "modulation": "OOK", "bit_pattern_hex": fp_hex,
                         "bit_length": 40, "rssi": -50, "decoded": None},
        "severity": "help", "match_threshold": 0.85, "enabled": True,
        "last_seen_at": None, "last_rssi": None, "press_count": 0,
        "created_at": now_utc().isoformat(), "created_by": None,
    })

    try:
        # Physical press 1: 8 frames at ~0.5s cadence (real Interlogix profile).
        seq = 500
        first = _press(kiosk_id, seq, fp_hex=fp_hex); seq += 1
        alert_a = first["alert_id"]
        assert first.get("echo_frame") is not True
        for _ in range(7):
            time.sleep(0.5)
            r = _press(kiosk_id, seq, fp_hex=fp_hex); seq += 1
            assert r["alert_id"] == alert_a
            assert r.get("echo_frame") is True

        doc = await db.alerts.find_one({"alert_id": alert_a}, {"_id": 0})
        assert doc["press_count"] == 1, "one physical press (8 frames) = one press_count"
        assert len(doc["presses"]) == 1

        # Every raw frame is still on record as evidence.
        frames = await db.rf_events.count_documents({"fingerprint.bit_pattern_hex": fp_hex})
        assert frames == 8, "all 8 raw RF frames must be persisted to rf_events (evidence never dropped)"

        # Physical press 2, after the echo window: a real separate press.
        time.sleep(PAST_ECHO_WINDOW)
        r = _press(kiosk_id, seq, fp_hex=fp_hex); seq += 1
        assert r["alert_id"] == alert_a
        assert r.get("echo_frame") is not True
        doc = await db.alerts.find_one({"alert_id": alert_a}, {"_id": 0})
        assert doc["press_count"] == 2
        assert len(doc["presses"]) == 2
    finally:
        await db.residents.delete_one({"resident_id": resident_id})
        await db.kiosks.delete_one({"kiosk_id": kiosk_id})
        await db.rf_devices.delete_one({"rf_device_id": rf_device_id})
        await db.alerts.delete_many({"resident_id": resident_id})
        await db.receipts.delete_many({"resident_id": resident_id})
        await db.rf_events.delete_many({"fingerprint.bit_pattern_hex": fp_hex})
        await db.resident_aria_leases.delete_many({"room": room})


async def _run_all():
    # Motor's AsyncIOMotorClient binds to the event loop of whichever
    # asyncio.run() call touches it first - a second, separate asyncio.run()
    # in the same process gets a fresh loop and raises "Event loop is
    # closed" against that cached client (same constraint the file this
    # replaces documented). All scenarios run inside ONE asyncio.run() call.
    await _run_reactivation_sequence()
    await _run_rf_echo_debounce()
    await _run_two_sources_one_event()
    await _run_staff_presence_mute()
    await _run_pattern_minimum_history()


def test_resident_event_model():
    asyncio.run(_run_all())
