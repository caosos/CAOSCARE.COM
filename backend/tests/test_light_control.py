"""Regression + acceptance tests for real Matter light control through
Aria's generic device contract (docs/PROJECT_STATE.md, 2026-09-05).

Two device fixtures are used deliberately:
  - Room 214's REAL bulb (dev_f8be14de18e3, protocol="home_assistant",
    endpoint="light.smart_multicolor_bulb") - the actual commissioned
    TP-Link Tapo L535E. Tests here send REAL commands to REAL hardware and
    assert on the REAL Home-Assistant read-back, not just HTTP 200.
  - Room 318's mock "Lamp" (capabilities power+brightness only, no
    color/color_temp) - used for the unsupported-capability and
    room-isolation checks so those stay fast/deterministic and don't
    depend on the physical bulb's current state.

Requires the local backend running with HA_BASE_URL/HA_TOKEN configured
and the real bulb reachable. Skips cleanly (not fails) if either
precondition isn't met, per every other test file's convention here.

Run with: pytest tests/test_light_control.py -q
"""
import os
import sys

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "http://127.0.0.1:8000").rstrip("/")
API = f"{BASE_URL}/api"

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

REAL_ROOM = "214"
REAL_LIGHT_ID = "dev_f8be14de18e3"
MOCK_ROOM = "318"


def _skip_if_unreachable():
    try:
        requests.get(f"{BASE_URL}/api/health", timeout=3).raise_for_status()
    except Exception:
        pytest.skip("backend not reachable")


def _skip_if_real_light_not_configured():
    r = requests.get(f"{API}/devices/public/by-room/{REAL_ROOM}", timeout=10)
    if r.status_code != 200:
        pytest.skip("Room 214 not seeded")
    light = next((d for d in r.json() if d["device_id"] == REAL_LIGHT_ID), None)
    if not light or light.get("protocol") != "home_assistant":
        pytest.skip("Room 214's real bulb isn't configured as protocol=home_assistant")
    return light


def _command(room, action, value, kind="light"):
    return requests.post(f"{API}/devices/public/room/{room}/command",
                          json={"action": action, "value": value, "kind": kind}, timeout=15)


class TestRealBulbCapabilities:
    """Requirement: power, brightness, color, color_temp, each independently
    verified against the real Home Assistant read-back - never HTTP 200 alone."""

    def test_power_on_then_off_verified_against_real_hardware(self):
        _skip_if_unreachable()
        _skip_if_real_light_not_configured()
        r_on = _command(REAL_ROOM, "power", "on")
        assert r_on.status_code == 200, r_on.text
        body = r_on.json()
        assert body["verified"] is True
        assert body["state"]["power"] == "on"

        r_off = _command(REAL_ROOM, "power", "off")
        assert r_off.status_code == 200, r_off.text
        assert r_off.json()["state"]["power"] == "off"

    def test_brightness_verified_against_real_hardware(self):
        _skip_if_unreachable()
        _skip_if_real_light_not_configured()
        _command(REAL_ROOM, "power", "on")
        r = _command(REAL_ROOM, "brightness", 50)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["verified"] is True
        assert abs(body["state"]["brightness"] - 50) <= 6

    def test_color_verified_against_real_hardware(self):
        _skip_if_unreachable()
        _skip_if_real_light_not_configured()
        _command(REAL_ROOM, "power", "on")
        r = _command(REAL_ROOM, "color", [0, 80, 255])  # blue
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["verified"] is True
        assert isinstance(body["state"]["color"], list) and len(body["state"]["color"]) == 3
        # A color command must not leave a stale color_temp behind.
        assert "color_temp" not in body["state"]

    def test_color_temp_verified_against_real_hardware(self):
        _skip_if_unreachable()
        _skip_if_real_light_not_configured()
        _command(REAL_ROOM, "power", "on")
        r = _command(REAL_ROOM, "color_temp", 2700)  # warm
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["verified"] is True
        assert abs(body["state"]["color_temp"] - 2700) <= 200
        # A color_temp command must not leave a stale color behind.
        assert "color" not in body["state"]

    def test_state_verification_failure_is_never_reported_as_success(self):
        """A command against an entity that doesn't exist must fail loudly
        (502), never a silent/optimistic 200 - the whole point of this
        feature (docs task: 'never report success if state can't be
        verified'). Uses a throwaway device pointed at a real but
        nonexistent HA entity, so it doesn't depend on forcing a timing
        failure against the real bulb."""
        _skip_if_unreachable()
        import asyncio
        from routes.auth import _issue_jwt
        from deps import db

        async def _owner():
            return await db.users.find_one({"role": "owner"}, {"_id": 0, "user_id": 1})

        owner = asyncio.run(_owner())
        if not owner:
            pytest.skip("no owner user seeded")
        sess = requests.Session()
        sess.headers.update({"Content-Type": "application/json", "Authorization": f"Bearer {_issue_jwt(owner['user_id'])}"})

        created = sess.post(f"{API}/devices", json={
            "label": "TEST fake light", "kind": "light", "protocol": "home_assistant",
            "room": "TEST-LIGHTFAIL", "endpoint": "light.does_not_really_exist_xyz",
            "capabilities": ["power"],
        }, timeout=10)
        assert created.status_code == 200, created.text
        device_id = created.json()["device_id"]
        try:
            r = sess.post(f"{API}/devices/{device_id}/command", json={"action": "power", "value": "on"}, timeout=15)
            assert r.status_code == 502, "a command against a nonexistent HA entity must fail, not silently succeed"
        finally:
            sess.delete(f"{API}/devices/{device_id}", timeout=10)


class TestRoomIsolationAndSelection:
    """Requirements: room-aware resolution, never cross-room, honest
    unsupported-capability behavior. Uses the mock light so it's fast and
    doesn't depend on the physical bulb's current state."""

    def test_command_to_one_room_light_does_not_touch_another_rooms_light(self):
        _skip_if_unreachable()
        before = requests.get(f"{API}/devices/public/by-room/{REAL_ROOM}", timeout=10)
        if before.status_code != 200:
            pytest.skip("Room 214 not seeded")
        real_light_before = next((d for d in before.json() if d["device_id"] == REAL_LIGHT_ID), None)
        if not real_light_before:
            pytest.skip("Room 214's light not seeded")
        state_before = real_light_before["state"].copy()

        r = _command(MOCK_ROOM, "brightness", 33)
        if r.status_code == 404:
            pytest.skip("Room 318 not seeded")
        assert r.status_code == 200, r.text

        after = requests.get(f"{API}/devices/public/by-room/{REAL_ROOM}", timeout=10).json()
        real_light_after = next(d for d in after if d["device_id"] == REAL_LIGHT_ID)
        assert real_light_after["state"] == state_before, "a command to Room 318 changed Room 214's light"

    def test_unsupported_capability_reported_honestly_not_silently_ignored(self):
        _skip_if_unreachable()
        r = _command(MOCK_ROOM, "color", [255, 0, 0])
        if r.status_code == 404:
            pytest.skip("Room 318 not seeded")
        # The mock lamp has no "color" capability - must be rejected, not
        # silently accepted and then do nothing.
        assert r.status_code == 400, r.text
        assert "color" in r.json()["detail"].lower()

    def test_selects_the_light_not_another_device_kind_in_the_same_room(self):
        _skip_if_unreachable()
        devices = requests.get(f"{API}/devices/public/by-room/{REAL_ROOM}", timeout=10)
        if devices.status_code != 200:
            pytest.skip("Room 214 not seeded")
        kinds = {d["kind"] for d in devices.json()}
        if "thermostat" not in kinds:
            pytest.skip("Room 214 doesn't have a thermostat to disambiguate against")
        r = _command(REAL_ROOM, "power", "on", kind="light")
        assert r.status_code == 200, r.text
        assert r.json()["device_id"] == REAL_LIGHT_ID
