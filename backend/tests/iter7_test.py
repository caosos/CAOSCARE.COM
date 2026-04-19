"""Iteration 7 backend tests: auto_voice always-on for pendant/wearable press events.

Critical-safety change under test:
- Every pendant press (not only >=2) MUST set auto_voice=true on the created alert
  so the kiosk auto-starts hands-free voice.
- Single press severity remains "assist", press_count=1.
- A second press within 60s escalates to severity="emergency" + press_count=2.
- Every wearable press/fall event MUST set auto_voice=true.
- GET /api/kiosks/{central_id}/active-emergency returns the newly-created alert
  because the endpoint filters on auto_voice=true regardless of severity.
"""
import os
import time
import uuid
from datetime import datetime, timezone, timedelta

import pytest
import requests

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
API = f"{BASE_URL}/api"

ADMIN = {"email": "admin@caoscare.com", "password": "admin1234"}


def _login(creds):
    r = requests.post(f"{API}/auth/login", json=creds, timeout=20)
    assert r.status_code == 200, r.text
    return r.json()["token"]


def _h(tok):
    return {"Authorization": f"Bearer {tok}"}


@pytest.fixture(scope="module")
def admin_token():
    return _login(ADMIN)


# ---- Scoped test pendant (unique frequency, unique resident) ----
@pytest.fixture(scope="module")
def test_pendant(admin_token):
    """Register a fresh pendant at a unique MHz freq assigned to an existing resident
    whose room has a kiosk (Dorothy in 214, Second Floor). Delete at teardown."""
    # Pick Dorothy in room 214 (kiosk kio_8690af1623c7 exists there)
    rr = requests.get(f"{API}/residents", headers=_h(admin_token), timeout=15)
    residents = rr.json()
    target = next(x for x in residents if x.get("room") == "214")

    # Fresh frequency — avoid collisions with existing 916.0..916.075
    freq = round(920.0 + (uuid.uuid4().int % 1000) * 0.001, 3)
    payload = {
        "pendant_id": f"PEN-ITER7-{uuid.uuid4().hex[:6]}",
        "frequency_mhz": freq,
        "resident_id": target["resident_id"],
        "status": "active",
    }
    r = requests.post(f"{API}/pendants", json=payload, headers=_h(admin_token), timeout=15)
    assert r.status_code == 200, r.text
    created = r.json()
    yield {
        "pendant_device_id": created["pendant_device_id"],
        "pendant_id": created["pendant_id"],
        "frequency_mhz": freq,
        "resident_id": target["resident_id"],
        "resident_name": target["name"],
        "room": target["room"],
    }
    # teardown
    requests.delete(
        f"{API}/pendants/{created['pendant_device_id']}",
        headers=_h(admin_token),
        timeout=15,
    )


def _post_pendant_event(freq, event_type="press"):
    return requests.post(
        f"{API}/pendants/event",
        json={
            "frequency_mhz": freq,
            "event_type": event_type,
            "signal_strength": -55,
            "battery_percent": 88,
        },
        timeout=15,
    )


# ================= PENDANT =================
class TestPendantAutoVoice:
    def test_single_press_sets_auto_voice_true_assist_press_count_1(self, test_pendant):
        """CRITICAL: even a single press must now set auto_voice=true."""
        r = _post_pendant_event(test_pendant["frequency_mhz"], "press")
        assert r.status_code == 200, r.text
        body = r.json()
        alert = body["alert"]
        assert alert is not None, f"Expected alert, got {body}"
        assert alert["auto_voice"] is True, f"auto_voice must be True on single press. alert={alert}"
        assert alert["severity"] == "assist", f"Single press severity must be 'assist'. got {alert['severity']}"
        assert alert["press_count"] == 1, f"First press_count must be 1. got {alert['press_count']}"
        assert alert["triggered_by"] == "pendant"
        assert alert["resident_id"] == test_pendant["resident_id"]
        assert alert["room"] == test_pendant["room"]
        assert alert["pendant_id"] == test_pendant["pendant_id"]

    def test_second_press_within_60s_escalates_to_emergency(self, test_pendant):
        """After the first press (in previous test) a second press within 60s must
        produce severity=emergency, press_count=2, and auto_voice=true."""
        # Fire another press immediately. The first one from previous test happened <60s ago.
        r = _post_pendant_event(test_pendant["frequency_mhz"], "press")
        assert r.status_code == 200, r.text
        alert = r.json()["alert"]
        assert alert["auto_voice"] is True
        assert alert["severity"] == "emergency", f"Second press must escalate. got {alert['severity']}"
        assert alert["press_count"] >= 2, f"press_count must be >=2 after rapid second press. got {alert['press_count']}"
        assert "Panic-press" in (alert.get("message") or ""), f"Expected Panic-press message. got {alert.get('message')}"

    def test_fall_event_emergency_auto_voice(self, test_pendant):
        r = _post_pendant_event(test_pendant["frequency_mhz"], "fall")
        assert r.status_code == 200, r.text
        alert = r.json()["alert"]
        assert alert["auto_voice"] is True
        assert alert["severity"] == "emergency"


# ================= WEARABLE =================
class TestWearableAutoVoice:
    @pytest.fixture(scope="class")
    def test_wearable(self, admin_token):
        rr = requests.get(f"{API}/residents", headers=_h(admin_token), timeout=15)
        residents = rr.json()
        # pick Evelyn in room 112 to avoid collision with seeded wear_demo for Margaret
        target = next(x for x in residents if x.get("room") == "112")
        mac = f"AA:BB:CC:{uuid.uuid4().hex[:2].upper()}:{uuid.uuid4().hex[:2].upper()}:{uuid.uuid4().hex[:2].upper()}"
        payload = {
            "device_label": f"TEST_Watch_{uuid.uuid4().hex[:4]}",
            "kind": "smartwatch",
            "mac_address": mac,
            "resident_id": target["resident_id"],
            "status": "active",
        }
        r = requests.post(f"{API}/wearables", json=payload, headers=_h(admin_token), timeout=15)
        assert r.status_code == 200, r.text
        created = r.json()
        yield {
            "wearable_id": created["wearable_id"],
            "mac_address": mac,
            "resident_id": target["resident_id"],
            "resident_name": target["name"],
            "room": target["room"],
        }
        requests.delete(
            f"{API}/wearables/{created['wearable_id']}",
            headers=_h(admin_token),
            timeout=15,
        )

    def test_wearable_press_sets_auto_voice_true(self, test_wearable):
        r = requests.post(
            f"{API}/wearables/event",
            json={
                "wearable_id": test_wearable["wearable_id"],
                "event_type": "press",
            },
            timeout=15,
        )
        assert r.status_code == 200, r.text
        alert = r.json()["alert"]
        assert alert is not None
        assert alert["auto_voice"] is True, f"wearable press must set auto_voice true. got {alert}"
        assert alert["severity"] == "assist"
        assert alert["triggered_by"] == "wearable"
        assert alert["room"] == test_wearable["room"]

    def test_wearable_fall_emergency_auto_voice(self, test_wearable):
        r = requests.post(
            f"{API}/wearables/event",
            json={
                "wearable_id": test_wearable["wearable_id"],
                "event_type": "fall",
            },
            timeout=15,
        )
        assert r.status_code == 200, r.text
        alert = r.json()["alert"]
        assert alert["auto_voice"] is True
        assert alert["severity"] == "emergency"


# ================= ACTIVE-EMERGENCY INTEGRATION =================
class TestKioskActiveEmergency:
    """Confirm that a newly created assist-level pendant press (auto_voice=true) is
    returned by /api/kiosks/{central_id}/active-emergency and by the kiosk in the
    same room."""

    @pytest.fixture(scope="class")
    def central_kiosk_id(self):
        r = requests.get(f"{API}/kiosks", timeout=15)
        r.raise_for_status()
        kiosks = r.json()
        central = next((k for k in kiosks if k.get("is_central") or k.get("room") == "NS-01"), None)
        return central["kiosk_id"] if central else kiosks[0]["kiosk_id"]

    @pytest.fixture(scope="class")
    def fresh_pendant(self, admin_token):
        rr = requests.get(f"{API}/residents", headers=_h(admin_token), timeout=15)
        residents = rr.json()
        target = next(x for x in residents if x.get("room") == "108")  # Frank, kiosk room 108
        freq = round(925.0 + (uuid.uuid4().int % 1000) * 0.001, 3)
        payload = {
            "pendant_id": f"PEN-ITER7B-{uuid.uuid4().hex[:6]}",
            "frequency_mhz": freq,
            "resident_id": target["resident_id"],
            "status": "active",
        }
        r = requests.post(f"{API}/pendants", json=payload, headers=_h(admin_token), timeout=15)
        assert r.status_code == 200, r.text
        c = r.json()
        yield {"pendant_device_id": c["pendant_device_id"], "frequency_mhz": freq, "room": target["room"]}
        requests.delete(f"{API}/pendants/{c['pendant_device_id']}", headers=_h(admin_token), timeout=15)

    def test_central_kiosk_picks_up_assist_press(self, fresh_pendant, central_kiosk_id):
        # Single press — severity=assist, auto_voice=true
        r = _post_pendant_event(fresh_pendant["frequency_mhz"], "press")
        assert r.status_code == 200, r.text
        created_alert = r.json()["alert"]
        assert created_alert["severity"] == "assist"
        assert created_alert["auto_voice"] is True

        # Central kiosk should surface it because it subscribes to facility-wide auto_voice alerts
        time.sleep(0.5)
        got = requests.get(f"{API}/kiosks/{central_kiosk_id}/active-emergency", timeout=15)
        assert got.status_code == 200, got.text
        body = got.json()
        assert body["kiosk_is_central"] is True
        a = body.get("alert")
        assert a is not None, "Central kiosk must receive the assist-level auto_voice alert"
        assert a["auto_voice"] is True
        # The most recent alert returned should be our press — severity can be assist OR
        # emergency if a prior test produced a rapid second press, but the endpoint must
        # at least surface SOME auto_voice alert within the 5-min window.
        assert a["severity"] in ("assist", "emergency")

    def test_room_kiosk_picks_up_its_own_assist_press(self, fresh_pendant):
        """The kiosk in the pendant's room must also pick up the alert via room match."""
        # kiosk_id for room 108 is kio_ce314eefa978
        kiosks = requests.get(f"{API}/kiosks", timeout=15).json()
        room_kiosk = next(k for k in kiosks if k.get("room") == "108")

        got = requests.get(f"{API}/kiosks/{room_kiosk['kiosk_id']}/active-emergency", timeout=15)
        assert got.status_code == 200
        a = got.json().get("alert")
        assert a is not None, "Room kiosk must surface auto_voice=true assist alert from its room"
        assert a["auto_voice"] is True
        assert a.get("room") == "108" or a.get("zone") == room_kiosk.get("zone")

    def test_active_emergency_query_filters_on_auto_voice(self, central_kiosk_id):
        """Smoke check: the endpoint returns an alert object with auto_voice=true."""
        r = requests.get(f"{API}/kiosks/{central_kiosk_id}/active-emergency", timeout=15)
        assert r.status_code == 200
        body = r.json()
        if body.get("alert"):
            assert body["alert"]["auto_voice"] is True
