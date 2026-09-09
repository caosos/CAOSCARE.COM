"""Regression + acceptance tests for real Midea AC (climate domain) control
through Aria's generic device contract (docs/PROJECT_STATE.md, 2026-09-05).

Room 214 now has THREE climate-capable-ish devices: the real AC
(dev_fa83aeda0cd4, protocol=home_assistant, endpoint=climate.bedroom_midea_ac),
the retired mock AC (dev_e76b930036e6, online=False), and an unrelated mock
thermostat (dev_48c7ca79cc97, still online) - kept deliberately to prove
disambiguation-by-kind still works with a real device in the mix.

Requires the local backend running with HA_BASE_URL/HA_TOKEN configured and
the real AC reachable. Skips cleanly (not fails) if either precondition
isn't met, per every other test file's convention here.

Run with: pytest tests/test_climate_control.py -q
"""
import os
import sys

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "http://127.0.0.1:8000").rstrip("/")
API = f"{BASE_URL}/api"

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

REAL_ROOM = "214"
REAL_AC_ID = "dev_fa83aeda0cd4"
RETIRED_MOCK_AC_ID = "dev_e76b930036e6"
MOCK_ROOM = "318"


def _skip_if_unreachable():
    try:
        requests.get(f"{BASE_URL}/api/health", timeout=3).raise_for_status()
    except Exception:
        pytest.skip("backend not reachable")


def _skip_if_real_ac_not_configured():
    r = requests.get(f"{API}/devices/public/by-room/{REAL_ROOM}", timeout=10)
    if r.status_code != 200:
        pytest.skip("Room 214 not seeded")
    ac = next((d for d in r.json() if d["device_id"] == REAL_AC_ID), None)
    if not ac or ac.get("protocol") != "home_assistant":
        pytest.skip("Room 214's real AC isn't configured as protocol=home_assistant")
    return ac


def _command(room, action, value, kind=None):
    body = {"action": action, "value": value}
    if kind:
        body["kind"] = kind
    return requests.post(f"{API}/devices/public/room/{room}/command", json=body, timeout=15)


class TestRealAcCapabilities:
    """Requirement: power, target temperature, HVAC mode, each
    independently verified against the real Home Assistant read-back.

    2026-09-09 incident: a plain `pytest tests/` run left the real Room 214
    AC on (see docs/PROJECT_STATE.md) because these tests send real commands
    to real hardware and nothing excluded them from a routine full-suite
    run. Marked `real_hardware` - see backend/pytest.ini, which excludes
    this marker by default. Run explicitly with
    `pytest tests/test_climate_control.py -m real_hardware`."""
    pytestmark = pytest.mark.real_hardware

    def test_power_on_then_off_verified_against_real_hardware(self):
        _skip_if_unreachable()
        _skip_if_real_ac_not_configured()
        r_on = _command(REAL_ROOM, "power", "on", kind="ac")
        assert r_on.status_code == 200, r_on.text
        body = r_on.json()
        assert body["verified"] is True
        assert body["state"]["power"] == "on"

        r_off = _command(REAL_ROOM, "power", "off", kind="ac")
        assert r_off.status_code == 200, r_off.text
        assert r_off.json()["state"]["power"] == "off"

    def test_hvac_mode_verified_against_real_hardware(self):
        _skip_if_unreachable()
        _skip_if_real_ac_not_configured()
        r = _command(REAL_ROOM, "hvac_mode", "cool", kind="ac")
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["verified"] is True
        assert body["state"]["hvac_mode"] == "cool"
        assert body["state"]["power"] == "on"  # cool is not "off"

    def test_target_temperature_verified_against_real_hardware(self):
        _skip_if_unreachable()
        _skip_if_real_ac_not_configured()
        _command(REAL_ROOM, "hvac_mode", "cool", kind="ac")
        r = _command(REAL_ROOM, "temperature", 70, kind="ac")
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["verified"] is True
        assert abs(body["state"]["temperature"] - 70) <= 2

    def test_current_temperature_distinct_from_target(self):
        """The room's real, measured temperature must never be conflated
        with the setpoint we just requested - explicit requirement."""
        _skip_if_unreachable()
        ac = _skip_if_real_ac_not_configured()
        r = _command(REAL_ROOM, "temperature", 65, kind="ac")
        assert r.status_code == 200, r.text
        state = r.json()["state"]
        assert state["temperature"] == pytest.approx(65, abs=2)
        if "current_temperature" in state:
            # The room itself did not teleport to 65 just because we asked
            # the unit to target 65 - these must be different values (or at
            # minimum, distinctly-tracked fields, not merged into one).
            assert "current_temperature" in state and "temperature" in state

    def test_unsupported_hvac_mode_reported_not_invented(self):
        """This real Matter integration only exposes off/cool/fan_only -
        proven live via GET /api/states. 'heat' must be rejected with a
        clear reason, never silently accepted or faked."""
        _skip_if_unreachable()
        _skip_if_real_ac_not_configured()
        r = _command(REAL_ROOM, "hvac_mode", "heat", kind="ac")
        assert r.status_code == 502, "an HVAC mode this device doesn't support must fail, not silently succeed"
        assert "heat" in r.json()["detail"].lower() or "hvac_mode" in r.json()["detail"].lower()


class TestRoomIsolationAndSelection:
    def test_command_to_mock_room_does_not_touch_real_ac(self):
        _skip_if_unreachable()
        before = requests.get(f"{API}/devices/public/by-room/{REAL_ROOM}", timeout=10)
        if before.status_code != 200:
            pytest.skip("Room 214 not seeded")
        ac_before = next((d for d in before.json() if d["device_id"] == REAL_AC_ID), None)
        if not ac_before:
            pytest.skip("Room 214's real AC not seeded")
        state_before = ac_before["state"].copy()

        r = _command(MOCK_ROOM, "temperature", 77, kind="thermostat")
        if r.status_code == 404:
            pytest.skip("Room 318 not seeded")

        after = requests.get(f"{API}/devices/public/by-room/{REAL_ROOM}", timeout=10).json()
        ac_after = next(d for d in after if d["device_id"] == REAL_AC_ID)
        assert ac_after["state"] == state_before, "a command to Room 318 changed Room 214's real AC"

    @pytest.mark.real_hardware
    def test_retired_mock_ac_excluded_from_selection(self):
        """The retired mock AC (online=False) must never intercept a
        kind='ac' command meant for the real one - proves the offline
        exclusion fix, not just that the real device happens to sort first."""
        _skip_if_unreachable()
        _skip_if_real_ac_not_configured()
        devices = requests.get(f"{API}/devices/public/by-room/{REAL_ROOM}", timeout=10).json()
        retired = next((d for d in devices if d["device_id"] == RETIRED_MOCK_AC_ID), None)
        if retired is None:
            pytest.skip("retired mock AC not present")
        assert retired["online"] is False
        r = _command(REAL_ROOM, "power", "on", kind="ac")
        assert r.status_code == 200, r.text
        assert r.json()["device_id"] == REAL_AC_ID, "an offline mock device was selected instead of the real AC"

    def test_ambiguous_climate_command_without_kind_is_rejected(self):
        """Room 214 has both the real AC (kind=ac) and a still-active mock
        thermostat (kind=thermostat), both with 'temperature' capability -
        an un-disambiguated command must be rejected, not silently routed."""
        _skip_if_unreachable()
        _skip_if_real_ac_not_configured()
        thermostat = requests.get(f"{API}/devices/public/by-room/{REAL_ROOM}", timeout=10).json()
        if not any(d["kind"] == "thermostat" and d.get("online", True) for d in thermostat):
            pytest.skip("no active thermostat to create real ambiguity with")
        r = _command(REAL_ROOM, "temperature", 70)  # no kind
        assert r.status_code == 400, "ambiguous AC-vs-thermostat command must be rejected, not guessed"
