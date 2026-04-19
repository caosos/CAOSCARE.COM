"""Iteration 5 tests: panic-press, central kiosk active-emergency,
staff tasks + templates, public device endpoints.
"""
import os
import time
import uuid
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://senior-locate.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN = {"email": "admin@caoscare.com", "password": "admin1234"}
NURSE = {"email": "nurse@caoscare.com", "password": "nurse1234"}


@pytest.fixture(scope="module")
def admin_headers():
    r = requests.post(f"{API}/auth/login", json=ADMIN)
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def nurse_headers():
    r = requests.post(f"{API}/auth/login", json=NURSE)
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}", "Content-Type": "application/json"}


# ---------- Panic press ----------
class TestPanicPress:
    def test_two_presses_within_60s_escalate(self, admin_headers):
        # Create fresh pendant + resident to avoid interference
        residents = requests.get(f"{API}/residents", headers=admin_headers).json()
        rid = residents[0]["resident_id"]
        freq = round(930.0 + (uuid.uuid4().int % 10000) / 1000.0, 3)
        p = requests.post(f"{API}/pendants", json={
            "pendant_id": f"TEST-PANIC-{uuid.uuid4().hex[:6]}",
            "frequency_mhz": freq,
            "resident_id": rid,
        }, headers=admin_headers).json()
        dev_id = p["pendant_device_id"]
        try:
            r1 = requests.post(f"{API}/pendants/event", json={
                "frequency_mhz": freq, "event_type": "press", "zone": "Hallway A"
            })
            assert r1.status_code == 200
            a1 = r1.json()["alert"]
            assert a1["severity"] == "assist"
            assert a1["auto_voice"] is False
            assert a1.get("press_count", 1) == 1

            r2 = requests.post(f"{API}/pendants/event", json={
                "frequency_mhz": freq, "event_type": "press", "zone": "Hallway A"
            })
            assert r2.status_code == 200
            a2 = r2.json()["alert"]
            assert a2["severity"] == "emergency", f"expected emergency, got {a2}"
            assert a2["auto_voice"] is True
            assert a2["press_count"] == 2
            assert a2["message"].startswith("Panic-press"), f"msg={a2['message']}"

            # resolve both
            requests.post(f"{API}/alerts/{a1['alert_id']}/resolve", headers=admin_headers)
            requests.post(f"{API}/alerts/{a2['alert_id']}/resolve", headers=admin_headers)
        finally:
            requests.delete(f"{API}/pendants/{dev_id}", headers=admin_headers)

    def test_fall_auto_voice_true(self, admin_headers):
        residents = requests.get(f"{API}/residents", headers=admin_headers).json()
        rid = residents[0]["resident_id"]
        freq = round(940.0 + (uuid.uuid4().int % 10000) / 1000.0, 3)
        p = requests.post(f"{API}/pendants", json={
            "pendant_id": f"TEST-FALL-{uuid.uuid4().hex[:6]}",
            "frequency_mhz": freq, "resident_id": rid,
        }, headers=admin_headers).json()
        dev_id = p["pendant_device_id"]
        try:
            r = requests.post(f"{API}/pendants/event", json={
                "frequency_mhz": freq, "event_type": "fall", "zone": "Bedroom"
            })
            assert r.status_code == 200
            a = r.json()["alert"]
            assert a["severity"] == "emergency"
            assert a["auto_voice"] is True
            requests.post(f"{API}/alerts/{a['alert_id']}/resolve", headers=admin_headers)
        finally:
            requests.delete(f"{API}/pendants/{dev_id}", headers=admin_headers)


# ---------- Kiosk active-emergency (central vs zonal) ----------
class TestActiveEmergency:
    def test_no_alert_returns_null(self, admin_headers):
        kiosks = requests.get(f"{API}/kiosks").json()
        # pick a non-central kiosk in a zone with no active emergency
        non_central = next((k for k in kiosks if not k.get("is_central")), None)
        assert non_central is not None
        # Resolve any active alerts in the zone first
        feed = requests.get(f"{API}/alerts/feed", headers=admin_headers).json()
        for a in feed:
            if a.get("zone") == non_central.get("zone") or a.get("room") == non_central.get("room"):
                requests.post(f"{API}/alerts/{a['alert_id']}/resolve", headers=admin_headers)
        r = requests.get(f"{API}/kiosks/{non_central['kiosk_id']}/active-emergency")
        assert r.status_code == 200
        body = r.json()
        assert "alert" in body and body["alert"] is None

    def test_central_kiosk_sees_any_facility_emergency(self, admin_headers):
        kiosks = requests.get(f"{API}/kiosks").json()
        central = next((k for k in kiosks if k.get("is_central")), None)
        assert central is not None, "Central Nurse Station not seeded"
        non_central = next((k for k in kiosks if not k.get("is_central")), None)
        assert non_central is not None

        # Trigger auto_voice emergency via fall on a fresh pendant in a far-off room
        residents = requests.get(f"{API}/residents", headers=admin_headers).json()
        rid = residents[0]["resident_id"]
        freq = round(950.0 + (uuid.uuid4().int % 10000) / 1000.0, 3)
        p = requests.post(f"{API}/pendants", json={
            "pendant_id": f"TEST-CEN-{uuid.uuid4().hex[:6]}",
            "frequency_mhz": freq, "resident_id": rid,
        }, headers=admin_headers).json()
        dev_id = p["pendant_device_id"]
        try:
            ev = requests.post(f"{API}/pendants/event", json={
                "frequency_mhz": freq, "event_type": "fall", "zone": "ZoneXYZ-FarAway"
            })
            assert ev.status_code == 200
            aid = ev.json()["alert"]["alert_id"]

            # Central kiosk must see it
            rc = requests.get(f"{API}/kiosks/{central['kiosk_id']}/active-emergency").json()
            assert rc["kiosk_is_central"] is True
            assert rc["alert"] is not None, "central kiosk should see any facility alert"
            assert rc["alert"]["alert_id"] == aid

            # Non-central kiosk (different zone/room) must NOT see it
            rn = requests.get(f"{API}/kiosks/{non_central['kiosk_id']}/active-emergency").json()
            assert rn["kiosk_is_central"] is False
            # either null or a different alert (not ours)
            assert (rn["alert"] is None) or (rn["alert"]["alert_id"] != aid)

            requests.post(f"{API}/alerts/{aid}/resolve", headers=admin_headers)
        finally:
            requests.delete(f"{API}/pendants/{dev_id}", headers=admin_headers)

    def test_kiosk_accepts_is_central_update(self, admin_headers):
        payload = {"name": "TEST_central", "room": "TCZ", "zone": "TestZoneCZ", "is_central": True}
        r = requests.post(f"{API}/kiosks", json=payload, headers=admin_headers)
        assert r.status_code == 200, r.text
        k = r.json()
        kid = k["kiosk_id"]
        assert k.get("is_central") is True
        # toggle off
        r2 = requests.put(f"{API}/kiosks/{kid}", json={**payload, "is_central": False}, headers=admin_headers)
        assert r2.status_code == 200
        assert r2.json().get("is_central") is False
        requests.delete(f"{API}/kiosks/{kid}", headers=admin_headers)


# ---------- Staff tasks ----------
class TestTasks:
    def test_staff_cannot_create(self, nurse_headers):
        r = requests.post(f"{API}/tasks", json={"title": "TEST_nope"}, headers=nurse_headers)
        assert r.status_code == 403

    def test_admin_creates_task_with_denorm(self, admin_headers):
        residents = requests.get(f"{API}/residents", headers=admin_headers).json()
        rid = residents[0]["resident_id"]
        staff_list = requests.get(f"{API}/staff", headers=admin_headers).json()
        assert len(staff_list) > 0
        uid = staff_list[0]["user_id"]

        payload = {
            "title": f"TEST_task_{uuid.uuid4().hex[:6]}",
            "description": "test desc",
            "category": "meds",
            "shift": "day",
            "resident_id": rid,
            "assigned_to": uid,
        }
        r = requests.post(f"{API}/tasks", json=payload, headers=admin_headers)
        assert r.status_code == 200, r.text
        t = r.json()
        assert t["title"] == payload["title"]
        assert t.get("assigned_name") == staff_list[0]["name"]
        assert t.get("resident_name") == residents[0]["name"]
        tid = t["task_id"]

        # start
        r = requests.post(f"{API}/tasks/{tid}/start", headers=admin_headers)
        assert r.status_code == 200
        s = r.json()
        assert s["status"] == "in_progress"
        assert s.get("started_at")

        time.sleep(1.2)

        # complete with notes
        r = requests.post(f"{API}/tasks/{tid}/complete",
                          json={"notes": "done well"}, headers=admin_headers)
        assert r.status_code == 200
        c = r.json()
        assert c["status"] == "completed"
        assert c.get("completed_by_name")
        assert c.get("notes") == "done well"
        assert c.get("duration_minutes") is not None

        requests.delete(f"{API}/tasks/{tid}", headers=admin_headers)

    def test_spawn_today_idempotent(self, admin_headers):
        r1 = requests.post(f"{API}/tasks/spawn-today", headers=admin_headers)
        assert r1.status_code == 200, r1.text
        # On a fresh seed first call may have been done already; run it again to be sure
        r2 = requests.post(f"{API}/tasks/spawn-today", headers=admin_headers)
        assert r2.status_code == 200
        assert r2.json()["created"] == 0, f"expected idempotent 0, got {r2.json()}"

    def test_list_staff_mine_only_inferred(self, admin_headers, nurse_headers):
        # Admin sees all
        admin_list = requests.get(f"{API}/tasks", headers=admin_headers).json()
        staff_list = requests.get(f"{API}/tasks", headers=nurse_headers).json()
        assert isinstance(admin_list, list) and isinstance(staff_list, list)
        # staff filter: all returned tasks (if any) must be assigned to nurse OR list may be empty
        me = requests.get(f"{API}/auth/me", headers=nurse_headers).json()
        my_id = me["user_id"]
        for t in staff_list:
            assert t.get("assigned_to") == my_id, f"staff sees another user's task: {t.get('assigned_to')} vs {my_id}"
        # admin list should be >= staff list
        assert len(admin_list) >= len(staff_list)

    def test_templates_crud(self, admin_headers):
        # List all
        lst = requests.get(f"{API}/tasks/templates/all", headers=admin_headers)
        assert lst.status_code == 200
        items = lst.json()
        assert isinstance(items, list)
        assert len(items) >= 1, "expected seeded templates"

        # Create
        payload = {
            "title": f"TEST_tpl_{uuid.uuid4().hex[:6]}",
            "description": "test",
            "category": "rounds",
            "shift": "day",
            "active": True,
        }
        c = requests.post(f"{API}/tasks/templates", json=payload, headers=admin_headers)
        assert c.status_code == 200, c.text
        tpl_id = c.json()["template_id"]

        # Delete
        d = requests.delete(f"{API}/tasks/templates/{tpl_id}", headers=admin_headers)
        assert d.status_code == 200


# ---------- Public device endpoints ----------
class TestPublicDevices:
    def test_public_by_room_101(self):
        r = requests.get(f"{API}/devices/public/by-room/101")
        assert r.status_code == 200
        items = r.json()
        assert isinstance(items, list) and len(items) >= 1
        for d in items:
            assert d.get("room") == "101"
            assert "device_id" in d

    def test_public_by_room_108(self):
        r = requests.get(f"{API}/devices/public/by-room/108")
        assert r.status_code == 200
        items = r.json()
        assert isinstance(items, list) and len(items) >= 1

    def test_public_room_command_updates_state(self, admin_headers):
        # Pick a device in room 101 with a power capability
        devs = requests.get(f"{API}/devices/public/by-room/101").json()
        pow_dev = next((d for d in devs if "power" in (d.get("capabilities") or [])), None)
        assert pow_dev is not None, f"no power device in room 101, have: {[d.get('label') for d in devs]}"
        new_val = not bool((pow_dev.get("state") or {}).get("power"))
        r = requests.post(f"{API}/devices/public/room/101/command",
                          json={"action": "power", "value": new_val})
        assert r.status_code == 200, r.text
        queued = r.json()
        assert queued["action"] == "power"
        assert queued["status"] == "queued"

        # Verify device state updated
        after = requests.get(f"{API}/devices/public/by-room/101").json()
        found = next((d for d in after if d["device_id"] == pow_dev["device_id"]), None)
        assert found is not None
        assert bool((found.get("state") or {}).get("power")) == new_val
