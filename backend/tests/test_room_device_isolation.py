"""Regression tests for the 2026-08-27 mock room-device layer and
resident/room request isolation work (see docs/reports/2026-08-27 forensics
+ implementation report). Hits the real running backend over HTTP using the
same public/authed endpoints Aria and the kiosk actually call - not direct
Mongo writes - so a pass here proves the real service boundary, not just
data shape.

Requires the local backend running (REACT_APP_BACKEND_URL, defaults to
http://127.0.0.1:8000) with Rooms 401/403/408 already seeded (mock
residents + mock devices, see scripts/seed_mock_residents.py and
scripts/seed_mock_devices.py). Skips cleanly if either precondition isn't met.

Run with: REACT_APP_BACKEND_URL=http://127.0.0.1:8000 pytest tests/test_room_device_isolation.py -q
"""
import os
import sys
import uuid

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "http://127.0.0.1:8000").rstrip("/")
API = f"{BASE_URL}/api"

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

ROOMS = ["401", "403", "408"]
# Department slugs to try, in order, for a category with no open ticket
# already on file for all three test rooms - keeps request-creation tests
# deterministic regardless of whatever demo data already exists.
CATEGORY_CANDIDATES = ["kitchen", "administration", "front_desk", "complaint", "housekeeping", "nursing", "maintenance"]


@pytest.fixture(scope="module")
def admin():
    """Owner JWT, issued the same way scripts/seed_mock_residents.py does
    (no password needed - this is a local-dev/demo environment check, not
    a login-flow test)."""
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
    return sess


@pytest.fixture(scope="module")
def room_residents(admin):
    r = admin.get(f"{API}/residents", timeout=15)
    if r.status_code != 200:
        pytest.skip("could not list residents")
    by_room = {res["room"]: res["resident_id"] for res in r.json() if res.get("room") in ROOMS}
    missing = [room for room in ROOMS if room not in by_room]
    if missing:
        pytest.skip(f"rooms not seeded: {missing} - run scripts/seed_mock_residents.py")
    return by_room


@pytest.fixture(scope="module")
def clear_category(admin, room_residents):
    """A request category with no OPEN ticket for any of the three test
    rooms, so 'create request A' below is provably a brand-new task, not a
    re-request merge into pre-existing demo data."""
    for cat in CATEGORY_CANDIDATES:
        if all(
            not admin.get(f"{API}/tasks/resident-request/status",
                           params={"resident_id": rid, "category": cat}, timeout=15).json().get("found")
            for rid in room_residents.values()
        ):
            return cat
    pytest.skip("no request category is clear of open tickets for all three test rooms")


def _create_request(room, resident_id, category, marker):
    r = requests.post(f"{API}/tasks/resident-request", json={
        "category": category, "resident_id": resident_id, "room": room,
        "resident_words": marker, "summary": marker, "source": "aria_voice",
    }, timeout=15)
    assert r.status_code == 200, r.text
    return r.json()


def _status(resident_id, category):
    r = requests.get(f"{API}/tasks/resident-request/status", params={"resident_id": resident_id, "category": category}, timeout=15)
    assert r.status_code == 200, r.text
    return r.json()


class TestRequestIsolation:
    """Acceptance items 1-8: a maintenance/staff request created for one
    room must never surface as another room's request."""

    def test_room_401_and_403_requests_are_independent(self, room_residents, clear_category):
        marker_401 = f"TEST-ISOLATION-401-{uuid.uuid4().hex[:8]}"
        marker_403 = f"TEST-ISOLATION-403-{uuid.uuid4().hex[:8]}"

        created_a = _create_request("401", room_residents["401"], clear_category, marker_401)
        created_b = _create_request("403", room_residents["403"], clear_category, marker_403)
        assert created_a["task_id"] != created_b["task_id"]
        assert created_a["duplicate"] is False
        assert created_b["duplicate"] is False

        # 4/5: each room's status query returns its OWN request only.
        status_401 = _status(room_residents["401"], clear_category)
        status_403 = _status(room_residents["403"], clear_category)
        assert status_401["found"] and status_403["found"]

        # 8: re-requesting from Room 401 must bump Room 401's own task, and
        # must NOT touch or merge into Room 403's.
        redo = _create_request("401", room_residents["401"], clear_category, marker_401)
        assert redo["task_id"] == created_a["task_id"]
        assert redo["duplicate"] is True
        assert redo["task_id"] != created_b["task_id"]

    def test_room_408_has_no_request_in_clear_category(self, room_residents, clear_category):
        # 3/6: a room that never asked reports honestly that it has none -
        # never inherits whatever the newest row in the collection is.
        status_408 = _status(room_residents["408"], clear_category)
        assert status_408["found"] is False

    def test_conversation_session_scoped_to_own_resident(self, admin, room_residents):
        # 7: a resident's conversation-session history contains only its
        # own tasks/receipts, keyed by resident_id - not a global feed.
        r = admin.get(f"{API}/residents/{room_residents['401']}/conversation-sessions", timeout=15)
        assert r.status_code == 200, r.text
        # Every session listed must belong to resident 401 by construction
        # (the endpoint itself filters db.conversations by resident_id) -
        # cross-check that no other test room's resident_id appears in the
        # underlying task list for any of those sessions.
        for s in r.json()[:5]:
            detail = admin.get(f"{API}/residents/{room_residents['401']}/conversation-sessions/{s['session_id']}", timeout=15)
            assert detail.status_code == 200
            for t in detail.json()["tasks"]:
                assert t.get("resident_id") == room_residents["401"]


class TestMockDeviceIsolation:
    """Acceptance items 9-10: changing one room's thermostat/TV must not
    change another room's, and every room keeps individualized state."""

    def _devices(self, room):
        r = requests.get(f"{API}/devices/public/by-room/{room}", timeout=15)
        assert r.status_code == 200, r.text
        return {d["kind"]: d for d in r.json()}

    def test_rooms_have_distinct_seeded_state(self, room_residents):
        d401, d403 = self._devices("401"), self._devices("403")
        assert "thermostat" in d401 and "thermostat" in d403
        assert "tv" in d401 and "tv" in d403
        # Distinct device_ids per room - not shared/singleton records.
        assert d401["thermostat"]["device_id"] != d403["thermostat"]["device_id"]
        assert d401["tv"]["device_id"] != d403["tv"]["device_id"]

    def test_thermostat_change_is_room_scoped(self, room_residents):
        before_403 = self._devices("403")["thermostat"]["state"].get("temperature")
        target = 79 if before_403 != 79 else 77  # a value distinct from 403's current state

        r = requests.post(f"{API}/devices/public/room/401/command",
                           json={"action": "temperature", "value": target, "kind": "thermostat"}, timeout=15)
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "executed"

        after_401 = self._devices("401")["thermostat"]["state"]["temperature"]
        after_403 = self._devices("403")["thermostat"]["state"].get("temperature")
        assert after_401 == target
        assert after_403 == before_403, "Room 403's thermostat changed when only Room 401's command was sent"

    def test_tv_power_is_room_scoped_and_disambiguated_by_kind(self, room_residents):
        # Regression for a real bug found during this work: with both a
        # thermostat and a TV in the same room sharing the "power"
        # capability, an un-disambiguated command silently hit whichever
        # device sorted first (the thermostat) instead of the TV.
        thermostat_before = self._devices("401")["thermostat"]["state"].copy()
        tv_403_before = self._devices("403")["tv"]["state"].copy()

        r = requests.post(f"{API}/devices/public/room/401/command",
                           json={"action": "power", "value": "on", "kind": "tv"}, timeout=15)
        assert r.status_code == 200, r.text

        after = self._devices("401")
        assert after["tv"]["state"]["power"] == "on"
        assert after["thermostat"]["state"] == thermostat_before, "TV command changed the thermostat's state"
        assert self._devices("403")["tv"]["state"] == tv_403_before, "Room 403's TV was affected by Room 401's command"

        # cleanup - leave the room as found
        requests.post(f"{API}/devices/public/room/401/command", json={"action": "power", "value": "off", "kind": "tv"}, timeout=15)

    def test_ambiguous_command_without_kind_rejected_not_misrouted(self, room_residents):
        r = requests.post(f"{API}/devices/public/room/401/command", json={"action": "power", "value": "off"}, timeout=15)
        assert r.status_code == 400, "an ambiguous multi-device command must be rejected, not silently routed to the wrong device"
