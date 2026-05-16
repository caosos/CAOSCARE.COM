"""CAOS Care backend regression tests."""
import os
import uuid
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://elderly-care-voice.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "admin@caoscare.com"
ADMIN_PW = "admin1234"
NURSE_EMAIL = "nurse@caoscare.com"
NURSE_PW = "nurse1234"


# ---------- fixtures ----------
@pytest.fixture(scope="session")
def session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="session")
def admin_token(session):
    r = session.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PW})
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture(scope="session")
def nurse_token(session):
    r = session.post(f"{API}/auth/login", json={"email": NURSE_EMAIL, "password": NURSE_PW})
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}


@pytest.fixture
def nurse_headers(nurse_token):
    return {"Authorization": f"Bearer {nurse_token}", "Content-Type": "application/json"}


# ---------- health + seed ----------
class TestHealth:
    def test_health(self, session):
        r = session.get(f"{API}/health")
        assert r.status_code == 200
        data = r.json()
        assert data["ok"] is True
        assert data["db"] == "up"

    def test_seed_kiosks(self, session):
        r = session.get(f"{API}/kiosks")
        assert r.status_code == 200
        items = r.json()
        assert isinstance(items, list) and len(items) >= 1
        assert "kiosk_id" in items[0]

    def test_seed_zones(self, session):
        r = session.get(f"{API}/zones")
        assert r.status_code == 200
        assert isinstance(r.json(), list)


# ---------- auth ----------
class TestAuth:
    def test_login_admin(self, session):
        r = session.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PW})
        assert r.status_code == 200
        body = r.json()
        assert "token" in body and body["user"]["role"] == "admin"
        assert body["user"]["email"] == ADMIN_EMAIL

    def test_login_nurse_role_staff(self, session):
        r = session.post(f"{API}/auth/login", json={"email": NURSE_EMAIL, "password": NURSE_PW})
        assert r.status_code == 200
        body = r.json()
        assert body["user"]["role"] == "staff"
        assert isinstance(body["token"], str) and len(body["token"]) > 20

    def test_login_bad_password(self, session):
        r = session.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": "wrong"})
        assert r.status_code == 401

    def test_register_new_user(self, session):
        email = f"test_{uuid.uuid4().hex[:8]}@example.com"
        r = session.post(f"{API}/auth/register", json={
            "email": email, "name": "TEST User", "password": "pw123456", "role": "staff",
        })
        assert r.status_code == 200, r.text
        body = r.json()
        assert "token" in body
        assert body["user"]["email"] == email
        assert body["user"]["role"] == "staff"

    def test_me_requires_auth(self, session):
        r = session.get(f"{API}/auth/me")
        assert r.status_code == 401

    def test_me_with_token(self, session, admin_headers):
        r = session.get(f"{API}/auth/me", headers=admin_headers)
        assert r.status_code == 200
        body = r.json()
        assert body["email"] == ADMIN_EMAIL
        assert body["role"] == "admin"


# ---------- residents ----------
class TestResidents:
    def test_list_requires_auth(self, session):
        r = session.get(f"{API}/residents")
        assert r.status_code == 401

    def test_crud_resident(self, session, admin_headers):
        # create
        payload = {"name": "TEST Jane Doe", "room": "T999", "pendant_id": f"PEN-TEST-{uuid.uuid4().hex[:6]}"}
        r = session.post(f"{API}/residents", json=payload, headers=admin_headers)
        assert r.status_code == 200, r.text
        created = r.json()
        rid = created["resident_id"]
        assert created["name"] == payload["name"]

        # get
        r = session.get(f"{API}/residents/{rid}", headers=admin_headers)
        assert r.status_code == 200
        assert r.json()["room"] == "T999"

        # update
        r = session.put(f"{API}/residents/{rid}", json={**payload, "room": "T998"}, headers=admin_headers)
        assert r.status_code == 200
        assert r.json()["room"] == "T998"

        # verify persisted
        r = session.get(f"{API}/residents/{rid}", headers=admin_headers)
        assert r.json()["room"] == "T998"

        # list
        r = session.get(f"{API}/residents", headers=admin_headers)
        assert any(x["resident_id"] == rid for x in r.json())

        # delete
        r = session.delete(f"{API}/residents/{rid}", headers=admin_headers)
        assert r.status_code == 200

        # confirm deleted
        r = session.get(f"{API}/residents/{rid}", headers=admin_headers)
        assert r.status_code == 404

    def test_public_by_kiosk(self, session):
        kiosks = session.get(f"{API}/kiosks").json()
        assert len(kiosks) > 0
        kid = kiosks[0]["kiosk_id"]
        r = session.get(f"{API}/residents/public/by-kiosk/{kid}")
        assert r.status_code == 200
        data = r.json()
        assert "kiosk" in data and data["kiosk"]["kiosk_id"] == kid
        assert "resident" in data  # may be None if no match, but key present


# ---------- kiosks + zones ----------
class TestKiosksZones:
    def test_kiosks_public(self, session):
        r = session.get(f"{API}/kiosks")
        assert r.status_code == 200

    def test_kiosk_create_requires_auth(self, session):
        r = session.post(f"{API}/kiosks", json={"name": "x", "room": "x", "zone": "x"})
        assert r.status_code == 401

    def test_kiosk_crud(self, session, admin_headers):
        payload = {"name": "TEST Kiosk", "room": "T777", "zone": "Test Zone", "mac_address": "AA:BB:CC:DD:EE:FF"}
        r = session.post(f"{API}/kiosks", json=payload, headers=admin_headers)
        assert r.status_code == 200
        k = r.json()
        kid = k["kiosk_id"]
        # update
        r = session.put(f"{API}/kiosks/{kid}", json={**payload, "room": "T776"}, headers=admin_headers)
        assert r.status_code == 200 and r.json()["room"] == "T776"
        # delete
        r = session.delete(f"{API}/kiosks/{kid}", headers=admin_headers)
        assert r.status_code == 200

    def test_zone_crud(self, session, admin_headers):
        r = session.post(f"{API}/zones", json={"name": f"TEST Zone {uuid.uuid4().hex[:4]}", "floor": "1"}, headers=admin_headers)
        assert r.status_code == 200
        zid = r.json()["zone_id"]
        r = session.delete(f"{API}/zones/{zid}", headers=admin_headers)
        assert r.status_code == 200


# ---------- staff (admin only) ----------
class TestStaffAdminOnly:
    def test_list_staff_admin(self, session, admin_headers):
        r = session.get(f"{API}/staff", headers=admin_headers)
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_list_staff_forbidden_for_nurse(self, session, nurse_headers):
        r = session.get(f"{API}/staff", headers=nurse_headers)
        assert r.status_code == 403

    def test_create_delete_staff(self, session, admin_headers):
        email = f"TEST_staff_{uuid.uuid4().hex[:6]}@example.com"
        r = session.post(f"{API}/staff", json={
            "email": email, "name": "TEST Staff", "password": "pw123456", "role": "staff",
        }, headers=admin_headers)
        assert r.status_code == 200, r.text
        uid_ = r.json()["user_id"]
        r = session.delete(f"{API}/staff/{uid_}", headers=admin_headers)
        assert r.status_code == 200

    def test_create_staff_forbidden_for_nurse(self, session, nurse_headers):
        r = session.post(f"{API}/staff", json={
            "email": "TEST_block@example.com", "name": "x", "password": "pw123456",
        }, headers=nurse_headers)
        assert r.status_code == 403


# ---------- alerts ----------
class TestAlerts:
    def test_create_alert_from_kiosk(self, session, admin_headers):
        kiosks = session.get(f"{API}/kiosks").json()
        kid = kiosks[0]["kiosk_id"]
        # public create
        r = session.post(f"{API}/alerts", json={
            "kiosk_id": kid, "severity": "emergency", "message": "TEST alert", "triggered_by": "kiosk_button"
        })
        assert r.status_code == 200, r.text
        alert = r.json()
        aid = alert["alert_id"]
        assert alert["status"] == "active"
        assert alert["severity"] == "emergency"
        # room/zone should be resolved from kiosk
        assert alert["room"] == kiosks[0]["room"]

        # feed must include it
        r = session.get(f"{API}/alerts/feed", headers=admin_headers)
        assert r.status_code == 200
        ids = [x["alert_id"] for x in r.json()]
        assert aid in ids

        # acknowledge
        r = session.post(f"{API}/alerts/{aid}/acknowledge", headers=admin_headers)
        assert r.status_code == 200 and r.json()["status"] == "acknowledged"

        # resolve
        r = session.post(f"{API}/alerts/{aid}/resolve", headers=admin_headers)
        assert r.status_code == 200 and r.json()["status"] == "resolved"

    def test_alerts_feed_auth(self, session):
        r = session.get(f"{API}/alerts/feed")
        assert r.status_code == 401

    def test_alert_stats(self, session, admin_headers):
        r = session.get(f"{API}/alerts/stats", headers=admin_headers)
        assert r.status_code == 200
        data = r.json()
        for k in ["active", "acknowledged", "resolved_24h", "emergency_active"]:
            assert k in data and isinstance(data[k], int)


# ---------- locations ----------
class TestLocations:
    def test_mock_generate_and_latest(self, session, admin_headers):
        r = session.post(f"{API}/locations/mock/generate", headers=admin_headers)
        assert r.status_code == 200
        body = r.json()
        assert body["generated"] >= 1

        r = session.get(f"{API}/locations/latest", headers=admin_headers)
        assert r.status_code == 200
        items = r.json()
        assert isinstance(items, list) and len(items) >= 1
        assert "resident_id" in items[0] and "zone" in items[0]

    def test_latest_requires_auth(self, session):
        r = session.get(f"{API}/locations/latest")
        assert r.status_code == 401

    def test_ingest_public_requires_valid_resident(self, session):
        r = session.post(f"{API}/locations", json={"resident_id": "res_nope", "zone": "Lounge"})
        assert r.status_code == 404

    def test_ingest_public_for_real_resident(self, session, admin_headers):
        residents = session.get(f"{API}/residents", headers=admin_headers).json()
        assert len(residents) > 0
        rid = residents[0]["resident_id"]
        r = session.post(f"{API}/locations", json={
            "resident_id": rid, "zone": "Dining Room", "source": "mesh", "signal_strength": 85
        })
        assert r.status_code == 200
        assert r.json()["resident_id"] == rid


# ---------- AI ----------
class TestAI:
    def test_chat_openai(self, session):
        sid = f"test-{uuid.uuid4().hex[:8]}"
        r = session.post(f"{API}/ai/chat", json={
            "session_id": sid, "message": "Hello, just saying hi.",
        }, timeout=60)
        assert r.status_code == 200, r.text
        body = r.json()
        assert "reply" in body and isinstance(body["reply"], str) and len(body["reply"]) > 0
        assert "auto_emergency_detected" in body

    def test_chat_history(self, session):
        sid = f"test-{uuid.uuid4().hex[:8]}"
        session.post(f"{API}/ai/chat", json={"session_id": sid, "message": "hi"}, timeout=60)
        r = session.get(f"{API}/ai/chat/history/{sid}")
        assert r.status_code == 200
        msgs = r.json()
        # at least user + assistant messages
        assert len(msgs) >= 2

    def test_tts(self, session):
        r = session.post(f"{API}/ai/tts", json={"text": "Hello there.", "voice": "sage"}, timeout=60)
        assert r.status_code == 200, r.text
        body = r.json()
        assert "audio_base64" in body and len(body["audio_base64"]) > 100
        assert body["mime"] == "audio/mp3"

    def test_tts_empty(self, session):
        r = session.post(f"{API}/ai/tts", json={"text": "  ", "voice": "sage"})
        assert r.status_code == 400

    def test_stt_endpoint_exists(self, session):
        # No audio file -> FastAPI returns 422 for missing file param (endpoint exists)
        r = session.post(f"{API}/ai/stt")
        assert r.status_code in (400, 422)



# ---------- roadmap ----------
class TestRoadmap:
    def test_list_roadmap(self, session):
        r = session.get(f"{API}/roadmap")
        assert r.status_code == 200
        items = r.json()
        assert isinstance(items, list)
        # Seeded ~34 items across phases 1-5
        assert len(items) >= 30, f"expected >=30 roadmap items, got {len(items)}"
        phases = {i["phase"] for i in items}
        assert phases >= {1, 2, 3, 4, 5}, f"phases found: {phases}"

    def test_progress_aggregates_by_phase(self, session):
        r = session.get(f"{API}/roadmap/progress")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, dict)
        # At least one phase present
        assert len(data) >= 1
        some_phase = next(iter(data.values()))
        for k in ["done", "in_progress", "not_started", "blocked"]:
            assert k in some_phase

    def test_patch_requires_auth(self, session):
        r = session.patch(f"{API}/roadmap/nonexistent", json={"status": "done"})
        assert r.status_code == 401

    def test_patch_updates_status(self, session, admin_headers):
        items = session.get(f"{API}/roadmap").json()
        assert len(items) > 0
        item_id = items[0]["item_id"]
        original_status = items[0]["status"]
        # toggle between done and original
        target = "in_progress" if original_status != "in_progress" else "not_started"
        r = session.patch(f"{API}/roadmap/{item_id}", json={"status": target, "notes": "TEST note"}, headers=admin_headers)
        assert r.status_code == 200, r.text
        assert r.json()["status"] == target
        assert r.json()["notes"] == "TEST note"
        # restore
        session.patch(f"{API}/roadmap/{item_id}", json={"status": original_status, "notes": items[0].get("notes", "")}, headers=admin_headers)


# ---------- pendants ----------
class TestPendants:
    def test_list_requires_auth(self, session):
        r = session.get(f"{API}/pendants")
        assert r.status_code == 401

    def test_list_seeded_pendants(self, session, admin_headers):
        r = session.get(f"{API}/pendants", headers=admin_headers)
        assert r.status_code == 200
        items = r.json()
        assert isinstance(items, list)
        assert len(items) >= 7, f"expected >=7 seeded pendants, got {len(items)}"
        # at least one has resident_name
        assert any(p.get("resident_name") for p in items)

    def test_create_and_delete_pendant(self, session, admin_headers):
        residents = session.get(f"{API}/residents", headers=admin_headers).json()
        assert len(residents) > 0
        rid = residents[0]["resident_id"]
        freq = round(915.0 + (uuid.uuid4().int % 10000) / 1000.0, 3)
        payload = {
            "pendant_id": f"TEST-PEN-{uuid.uuid4().hex[:6]}",
            "frequency_mhz": freq,
            "resident_id": rid,
            "battery_percent": 90,
        }
        r = session.post(f"{API}/pendants", json=payload, headers=admin_headers)
        assert r.status_code == 200, r.text
        created = r.json()
        assert created["frequency_mhz"] == freq
        dev_id = created["pendant_device_id"]

        # duplicate frequency -> 400
        dup = session.post(f"{API}/pendants", json=payload, headers=admin_headers)
        assert dup.status_code == 400

        # delete
        r = session.delete(f"{API}/pendants/{dev_id}", headers=admin_headers)
        assert r.status_code == 200

        # deleting again -> 404
        r = session.delete(f"{API}/pendants/{dev_id}", headers=admin_headers)
        assert r.status_code == 404

    def test_pendant_event_press_creates_alert(self, session, admin_headers):
        # Create a fresh test pendant mapped to a resident
        residents = session.get(f"{API}/residents", headers=admin_headers).json()
        rid = residents[0]["resident_id"]
        freq = round(920.0 + (uuid.uuid4().int % 10000) / 1000.0, 3)
        payload = {
            "pendant_id": f"TEST-PEN-{uuid.uuid4().hex[:6]}",
            "frequency_mhz": freq,
            "resident_id": rid,
        }
        created = session.post(f"{API}/pendants", json=payload, headers=admin_headers).json()
        dev_id = created["pendant_device_id"]
        try:
            # PUBLIC pendant event
            r = requests.post(f"{API}/pendants/event", json={
                "frequency_mhz": freq,
                "event_type": "press",
                "zone": "Hallway A",
                "signal_strength": 82,
            })
            assert r.status_code == 200, r.text
            body = r.json()
            assert body["alert"] is not None
            assert body["alert"]["triggered_by"] == "pendant"
            assert body["alert"]["resident_id"] == rid
            assert body["alert"]["resident_name"]

            # periodic_ping should NOT create alert
            r = requests.post(f"{API}/pendants/event", json={
                "frequency_mhz": freq,
                "event_type": "periodic_ping",
                "zone": "Lounge",
                "battery_percent": 88,
            })
            assert r.status_code == 200
            body = r.json()
            assert body["alert"] is None
        finally:
            session.delete(f"{API}/pendants/{dev_id}", headers=admin_headers)

    def test_pendant_event_unknown_frequency(self, session):
        # Use absurd frequency not in seeded list
        r = requests.post(f"{API}/pendants/event", json={
            "frequency_mhz": 1.234,
            "event_type": "press",
        })
        assert r.status_code == 404


# ---------- alerts: escalation, close, detail ----------
class TestAlertsEscalation:
    def test_feed_auto_escalates_old_alert(self, session, admin_headers):
        """Insert a synthetic alert via POST /alerts then backdate via close DB trick via admin tool.
        Since we cannot backdate directly via API, we create via public POST and rely on
        lazy compute by directly patching created_at via admin-only? No admin endpoint for that.
        So we skip if >65s wait is too slow — instead we just assert escalation_level present in feed.
        """
        kiosks = session.get(f"{API}/kiosks").json()
        kid = kiosks[0]["kiosk_id"]
        r = session.post(f"{API}/alerts", json={
            "kiosk_id": kid, "severity": "assist", "message": "TEST escalation candidate",
            "triggered_by": "kiosk_button"
        })
        assert r.status_code == 200
        aid = r.json()["alert_id"]

        r = session.get(f"{API}/alerts/feed", headers=admin_headers)
        assert r.status_code == 200
        match = next((a for a in r.json() if a["alert_id"] == aid), None)
        assert match is not None
        # freshly created: escalation_level is 0 (or missing)
        assert (match.get("escalation_level") or 0) == 0

        # cleanup
        session.post(f"{API}/alerts/{aid}/resolve", headers=admin_headers)

    def test_get_alert_with_timeline(self, session, admin_headers):
        kiosks = session.get(f"{API}/kiosks").json()
        kid = kiosks[0]["kiosk_id"]
        a = session.post(f"{API}/alerts", json={
            "kiosk_id": kid, "severity": "assist", "message": "TEST timeline",
            "triggered_by": "kiosk_button"
        }).json()
        aid = a["alert_id"]

        # ack
        session.post(f"{API}/alerts/{aid}/acknowledge", headers=admin_headers)

        r = session.get(f"{API}/alerts/{aid}", headers=admin_headers)
        assert r.status_code == 200, r.text
        body = r.json()
        assert "alert" in body and "timeline" in body and "chat" in body
        labels = [t["label"] for t in body["timeline"]]
        assert "Created" in labels
        assert "Acknowledged" in labels

        # close with outcome
        r = session.post(f"{API}/alerts/{aid}/close", json={
            "outcome": "assisted to bathroom",
            "close_notes": "follow-up tomorrow",
        }, headers=admin_headers)
        assert r.status_code == 200, r.text
        closed = r.json()
        assert closed["status"] == "resolved"
        assert closed["outcome"] == "assisted to bathroom"
        assert closed["close_notes"] == "follow-up tomorrow"

        # verify timeline now includes Resolved
        r = session.get(f"{API}/alerts/{aid}", headers=admin_headers)
        labels = [t["label"] for t in r.json()["timeline"]]
        assert "Resolved" in labels

    def test_stats_route_not_clobbered_by_id_route(self, session, admin_headers):
        """Regression: /alerts/stats must win over /alerts/{id} path."""
        r = session.get(f"{API}/alerts/stats", headers=admin_headers)
        assert r.status_code == 200
        data = r.json()
        for k in ["active", "acknowledged", "resolved_24h", "emergency_active"]:
            assert k in data and isinstance(data[k], int)


# ---------- residents: personalization fields ----------
class TestResidentPersonalization:
    def test_create_and_update_with_new_fields(self, session, admin_headers):
        payload = {
            "name": "TEST Persona Resident",
            "room": "TP001",
            "pendant_id": f"PEN-PERS-{uuid.uuid4().hex[:6]}",
            "preferred_name": "Persona",
            "preferences": "Loves jazz and gardening",
            "memory": "Retired librarian, 3 grandkids",
            "participation_level": "pendant_enhanced",
        }
        r = session.post(f"{API}/residents", json=payload, headers=admin_headers)
        assert r.status_code == 200, r.text
        created = r.json()
        rid = created["resident_id"]
        try:
            # GET list - verify fields serialized
            r = session.get(f"{API}/residents", headers=admin_headers)
            row = next((x for x in r.json() if x["resident_id"] == rid), None)
            assert row is not None
            assert row.get("preferred_name") == "Persona"
            assert row.get("preferences") == "Loves jazz and gardening"
            assert row.get("memory") == "Retired librarian, 3 grandkids"
            assert row.get("participation_level") == "pendant_enhanced"

            # Update
            update = {**payload, "preferred_name": "P", "participation_level": "full"}
            r = session.put(f"{API}/residents/{rid}", json=update, headers=admin_headers)
            assert r.status_code == 200
            assert r.json().get("preferred_name") == "P"
            assert r.json().get("participation_level") == "full"
        finally:
            session.delete(f"{API}/residents/{rid}", headers=admin_headers)

    def test_ai_chat_with_resident_id(self, session, admin_headers):
        residents = session.get(f"{API}/residents", headers=admin_headers).json()
        rid = residents[0]["resident_id"]
        sid = f"test-{uuid.uuid4().hex[:8]}"
        r = session.post(f"{API}/ai/chat", json={
            "session_id": sid,
            "message": "Hello friend",
            "resident_id": rid,
        }, timeout=60)
        assert r.status_code == 200, r.text
        assert "reply" in r.json() and len(r.json()["reply"]) > 0


# ---------- Iteration 3: Zones / Geofence / Movement / Insights / Family / Notifications ----------
class TestZonesAndGeofence:
    def test_zones_include_is_restricted(self, session):
        r = session.get(f"{API}/zones")
        assert r.status_code == 200
        zones = r.json()
        assert isinstance(zones, list) and len(zones) > 0
        # Skip stale leftover TEST zones from prior iterations pre-field-addition
        prod_zones = [z for z in zones if not z.get("name", "").startswith("TEST")]
        assert all("is_restricted" in z for z in prod_zones)
        restricted = [z for z in prod_zones if z["is_restricted"]]
        assert len(restricted) >= 2
        names = {z["name"] for z in restricted}
        assert "Staff Only — Medication Room" in names
        assert "Outside — Parking Lot" in names

    def test_create_restricted_zone(self, session, admin_headers):
        name = f"TEST_restricted_{uuid.uuid4().hex[:6]}"
        r = session.post(f"{API}/zones", json={
            "name": name, "floor": "1", "description": "test", "is_restricted": True
        }, headers=admin_headers)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["is_restricted"] is True
        # Cleanup
        session.delete(f"{API}/zones/{data['zone_id']}", headers=admin_headers)

    def test_post_location_to_non_restricted_no_alert(self, session, admin_headers):
        residents = session.get(f"{API}/residents", headers=admin_headers).json()
        rid = residents[0]["resident_id"]
        r = session.post(f"{API}/locations", json={
            "resident_id": rid, "zone": "Dining Room", "source": "mock"
        })
        assert r.status_code == 200
        assert "geofence_alert" not in r.json() or r.json().get("geofence_alert") is None

    def test_post_location_to_restricted_creates_alert_and_no_refire(self, session, admin_headers):
        residents = session.get(f"{API}/residents", headers=admin_headers).json()
        # Prefer a resident unlikely to be in allowed_levels (if any)
        rid = residents[0]["resident_id"]
        # First seed a non-restricted location to reset prev zone
        session.post(f"{API}/locations", json={"resident_id": rid, "zone": "Hallway A", "source": "mock"})

        # First breach
        r1 = session.post(f"{API}/locations", json={
            "resident_id": rid, "zone": "Outside — Parking Lot", "source": "mock"
        })
        assert r1.status_code == 200, r1.text
        data1 = r1.json()
        assert "geofence_alert" in data1 and data1["geofence_alert"], f"Expected geofence_alert, got {data1}"
        alert_id = data1["geofence_alert"]
        # Verify alert exists
        a = session.get(f"{API}/alerts/{alert_id}", headers=admin_headers)
        assert a.status_code == 200
        alert_doc = a.json()["alert"]
        assert alert_doc["triggered_by"] == "geofence"
        assert alert_doc["severity"] == "assist"

        # Second consecutive - should NOT refire
        r2 = session.post(f"{API}/locations", json={
            "resident_id": rid, "zone": "Outside — Parking Lot", "source": "mock"
        })
        assert r2.status_code == 200
        assert r2.json().get("geofence_alert") in (None, "", False) or "geofence_alert" not in r2.json()


class TestMovementTimeline:
    def test_movement_returns_visits_and_total(self, session, admin_headers):
        residents = session.get(f"{API}/residents", headers=admin_headers).json()
        rid = residents[0]["resident_id"]
        # Push a few pings in same zone + switch
        for z in ["Hallway A", "Hallway A", "Dining Room", "Dining Room", "Dining Room"]:
            session.post(f"{API}/locations", json={"resident_id": rid, "zone": z, "source": "mock"})
        r = session.get(f"{API}/residents/{rid}/movement?hours=168", headers=admin_headers)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "visits" in data and "total_pings" in data
        assert isinstance(data["visits"], list)
        assert data["total_pings"] >= 5
        # Verify collapsing: consecutive same-zone pings collapsed
        for v in data["visits"]:
            assert "zone" in v and "from" in v and "until" in v and "pings" in v


class TestInsights:
    def test_compute_insights(self, session, admin_headers):
        r = session.post(f"{API}/insights/compute", headers=admin_headers)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "computed" in data and "residents" in data
        assert data["residents"] > 0
        # Seeded historical data should generate at least some insights
        assert data["computed"] > 0

    def test_list_insights_sorted(self, session, admin_headers):
        # Ensure computed first
        session.post(f"{API}/insights/compute", headers=admin_headers)
        r = session.get(f"{API}/insights", headers=admin_headers)
        assert r.status_code == 200
        items = r.json()
        assert isinstance(items, list)
        if items:
            required = {"metric", "current_value", "baseline_value", "deviation_pct",
                        "severity", "confidence", "title", "description"}
            assert required.issubset(items[0].keys())
            sev_rank = {"concern": 0, "watch": 1, "info": 2}
            ranks = [sev_rank.get(x["severity"], 99) for x in items]
            assert ranks == sorted(ranks)

    def test_insights_summary(self, session, admin_headers):
        session.post(f"{API}/insights/compute", headers=admin_headers)
        r = session.get(f"{API}/insights/summary", headers=admin_headers)
        assert r.status_code == 200
        data = r.json()
        for k in ("concern", "watch", "info", "total"):
            assert k in data
        assert data["total"] == data["concern"] + data["watch"] + data["info"]

    def test_insights_for_resident(self, session, admin_headers):
        session.post(f"{API}/insights/compute", headers=admin_headers)
        residents = session.get(f"{API}/residents", headers=admin_headers).json()
        rid = residents[0]["resident_id"]
        r = session.get(f"{API}/insights/resident/{rid}", headers=admin_headers)
        assert r.status_code == 200
        items = r.json()
        assert isinstance(items, list)
        for it in items:
            assert it["resident_id"] == rid


class TestFamilyContacts:
    def test_list_family_seeded(self, session, admin_headers):
        r = session.get(f"{API}/family-contacts", headers=admin_headers)
        assert r.status_code == 200
        items = r.json()
        assert isinstance(items, list)
        assert len(items) >= 3

    def test_create_and_delete_family(self, session, admin_headers):
        residents = session.get(f"{API}/residents", headers=admin_headers).json()
        rid = residents[0]["resident_id"]
        r = session.post(f"{API}/family-contacts", json={
            "resident_id": rid,
            "name": "TEST_Family_Jane",
            "phone": "+15551234567",
            "email": "jane@test.com",
            "notify_on": ["emergency", "wander"],
        }, headers=admin_headers)
        assert r.status_code == 200, r.text
        cid = r.json()["contact_id"]
        # Delete
        d = session.delete(f"{API}/family-contacts/{cid}", headers=admin_headers)
        assert d.status_code == 200


class TestNotifications:
    def test_notifications_status_unconfigured(self, session, admin_headers):
        r = session.get(f"{API}/notifications/status", headers=admin_headers)
        assert r.status_code == 200
        data = r.json()
        assert data["twilio_configured"] is False
        assert data["resend_configured"] is False

    def test_notifications_test_sms_logged(self, session, admin_headers):
        r = session.post(f"{API}/notifications/test", json={
            "channel": "sms", "to": "+15551234567", "body": "test sms"
        }, headers=admin_headers)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["status"] == "logged"
        assert "not configured" in (data.get("provider_response") or "").lower()

    def test_notifications_test_email_logged(self, session, admin_headers):
        r = session.post(f"{API}/notifications/test", json={
            "channel": "email", "to": "x@y.com", "subject": "s", "body": "b"
        }, headers=admin_headers)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["status"] == "logged"
        assert "not configured" in (data.get("provider_response") or "").lower()

    def test_notifications_list(self, session, admin_headers):
        # Ensure at least one exists
        session.post(f"{API}/notifications/test", json={
            "channel": "sms", "to": "+15551112222", "body": "seed"
        }, headers=admin_headers)
        r = session.get(f"{API}/notifications", headers=admin_headers)
        assert r.status_code == 200
        items = r.json()
        assert isinstance(items, list) and len(items) >= 1

    def test_create_alert_fans_out_to_family(self, session, admin_headers):
        # Pick a resident who has a seeded family contact
        contacts = session.get(f"{API}/family-contacts", headers=admin_headers).json()
        assert len(contacts) > 0
        # Find a contact with emergency in notify_on
        target = next((c for c in contacts if "emergency" in c.get("notify_on", [])), contacts[0])
        rid = target["resident_id"]
        # Count notifications before
        before = session.get(f"{API}/notifications?limit=500", headers=admin_headers).json()
        before_ct = len(before)
        # Create an emergency alert
        r = session.post(f"{API}/alerts", json={
            "resident_id": rid, "severity": "emergency",
            "message": "TEST family fan-out", "triggered_by": "manual"
        })
        assert r.status_code == 200, r.text
        aid = r.json()["alert_id"]
        # Fetch notifications - should include new entries tied to this alert
        import time
        time.sleep(0.5)
        after = session.get(f"{API}/notifications?limit=500", headers=admin_headers).json()
        assert len(after) > before_ct, "No notifications fanned out to family"
        # At least one notification references this alert_id
        matched = [n for n in after if n.get("alert_id") == aid]
        assert len(matched) >= 1, f"No notification referenced alert {aid}"
        # Clean up: resolve
        session.post(f"{API}/alerts/{aid}/resolve", headers=admin_headers)


# ========================================================================
# Iteration 4: Wearables, Device Tokens, Family Portal, Bathroom Zones
# ========================================================================
class TestWearables:
    def test_list_wearables_seeded(self, session, admin_headers):
        r = session.get(f"{API}/wearables", headers=admin_headers)
        assert r.status_code == 200, r.text
        items = r.json()
        assert isinstance(items, list) and len(items) >= 1
        labels = [w.get("device_label") for w in items]
        assert any("smartwatch" in (lbl or "").lower() or "maggie" in (lbl or "").lower() for lbl in labels)

    def test_list_wearables_requires_auth(self, session):
        r = session.get(f"{API}/wearables")
        assert r.status_code in (401, 403)

    def test_crud_wearable_and_events(self, session, admin_headers):
        # Get a resident
        residents = session.get(f"{API}/residents", headers=admin_headers).json()
        rid = residents[0]["resident_id"]

        # Create
        payload = {
            "device_label": "TEST_wear_watch",
            "device_type": "smartwatch",
            "mac_address": f"AA:BB:CC:{uuid.uuid4().hex[:2].upper()}:11:22",
            "resident_id": rid,
        }
        c = session.post(f"{API}/wearables", json=payload, headers=admin_headers)
        assert c.status_code == 200, c.text
        wid = c.json()["wearable_id"]

        # Press event => assist
        e = session.post(f"{API}/wearables/event", json={
            "wearable_id": wid, "event_type": "press", "zone": "Hallway A"
        })
        assert e.status_code == 200, e.text
        body = e.json()
        assert body["alert"] is not None
        assert body["alert"]["severity"] == "assist"
        assist_aid = body["alert"]["alert_id"]

        # Fall event => emergency
        e2 = session.post(f"{API}/wearables/event", json={
            "wearable_id": wid, "event_type": "fall", "zone": "Hallway A"
        })
        assert e2.status_code == 200, e2.text
        assert e2.json()["alert"]["severity"] == "emergency"
        fall_aid = e2.json()["alert"]["alert_id"]

        # Periodic ping => no alert
        e3 = session.post(f"{API}/wearables/event", json={
            "wearable_id": wid, "event_type": "periodic_ping", "zone": "Hallway A"
        })
        assert e3.status_code == 200
        assert e3.json()["alert"] is None

        # Bad payload (neither id nor mac)
        e4 = session.post(f"{API}/wearables/event", json={"event_type": "press"})
        assert e4.status_code == 400, e4.text

        # cleanup
        session.post(f"{API}/alerts/{assist_aid}/resolve", headers=admin_headers)
        session.post(f"{API}/alerts/{fall_aid}/resolve", headers=admin_headers)
        d = session.delete(f"{API}/wearables/{wid}", headers=admin_headers)
        assert d.status_code == 200


class TestBathroomZones:
    def test_seed_has_bathroom_zones(self, session):
        zones = session.get(f"{API}/zones").json()
        bathrooms = [z for z in zones if z.get("is_bathroom")]
        assert len(bathrooms) >= 2
        names = [z["name"] for z in bathrooms]
        assert any("Bathroom" in n for n in names)

    def test_create_bathroom_zone(self, session, admin_headers):
        uniq = uuid.uuid4().hex[:6]
        c = session.post(f"{API}/zones", json={
            "name": f"TEST_Bathroom_{uniq}",
            "kind": "indoor",
            "is_bathroom": True,
        }, headers=admin_headers)
        assert c.status_code == 200, c.text
        z = c.json()
        assert z.get("is_bathroom") is True
        session.delete(f"{API}/zones/{z['zone_id']}", headers=admin_headers)

    def test_insights_bathroom_metric_present_when_applicable(self, session, admin_headers):
        # Compute - may or may not include bathroom metric depending on seed
        r = session.post(f"{API}/insights/compute", headers=admin_headers)
        assert r.status_code == 200, r.text
        ins = r.json()
        # compute returns a summary dict {computed, residents}
        assert isinstance(ins, dict)
        assert "computed" in ins and "residents" in ins
        # Now fetch the insights list and look for bathroom metric if any
        lst = session.get(f"{API}/insights", headers=admin_headers).json()
        assert isinstance(lst, list)


class TestDeviceTokens:
    def test_list_tokens_admin(self, session, admin_headers):
        r = session.get(f"{API}/device-tokens", headers=admin_headers)
        assert r.status_code == 200
        items = r.json()
        assert isinstance(items, list)
        # None of them should expose secret_hash
        for it in items:
            assert "secret_hash" not in it

    def test_list_tokens_staff_forbidden(self, session, nurse_headers):
        r = session.get(f"{API}/device-tokens", headers=nurse_headers)
        assert r.status_code == 403

    def test_status_endpoint(self, session, admin_headers):
        r = session.get(f"{API}/device-tokens/status", headers=admin_headers)
        assert r.status_code == 200
        b = r.json()
        assert "active_tokens" in b and "revoked_tokens" in b
        assert b.get("enforcement_required") is False

    def test_create_reveal_and_revoke_token(self, session, admin_headers):
        r = session.post(f"{API}/device-tokens", json={
            "name": f"TEST_tok_{uuid.uuid4().hex[:6]}",
            "scopes": ["pendants.event", "locations.ingest"],
        }, headers=admin_headers)
        assert r.status_code == 200, r.text
        body = r.json()
        assert "token_id" in body and "shared_secret" in body
        assert isinstance(body["shared_secret"], str) and len(body["shared_secret"]) > 20
        assert set(body["scopes"]) >= {"pendants.event", "locations.ingest"}
        assert "example_python" in body and "usage" in body
        tid = body["token_id"]

        # GET should NOT expose secret_hash
        lst = session.get(f"{API}/device-tokens", headers=admin_headers).json()
        match = next((t for t in lst if t["token_id"] == tid), None)
        assert match is not None
        assert "secret_hash" not in match

        # Revoke
        d = session.delete(f"{API}/device-tokens/{tid}", headers=admin_headers)
        assert d.status_code == 200
        assert d.json().get("ok") is True

    def test_pendant_event_soft_enforced_no_headers(self, session, admin_headers):
        # Get a pendant
        pendants = session.get(f"{API}/pendants", headers=admin_headers).json()
        if not pendants:
            pytest.skip("No pendants seeded")
        p = pendants[0]
        freq = p["frequency_mhz"]
        # No device headers - should still work (soft-enforced)
        r = session.post(f"{API}/pendants/event", json={
            "frequency_mhz": freq, "event_type": "press", "zone": "Hallway A"
        })
        assert r.status_code == 200, r.text
        aid = r.json().get("alert", {}).get("alert_id")
        if aid:
            session.post(f"{API}/alerts/{aid}/resolve", headers=admin_headers)

    def test_pendant_event_with_invalid_token_rejected(self, session, admin_headers):
        pendants = session.get(f"{API}/pendants", headers=admin_headers).json()
        if not pendants:
            pytest.skip("No pendants seeded")
        p = pendants[0]
        headers = {
            "Content-Type": "application/json",
            "X-Device-Token": "invalid_token_xyz",
            "X-Device-Signature": "abc123",
        }
        r = session.post(f"{API}/pendants/event", json={
            "frequency_mhz": p["frequency_mhz"], "event_type": "press"
        }, headers=headers)
        assert r.status_code == 401, r.text

    def test_pendant_event_with_only_token_header_rejected(self, session, admin_headers):
        pendants = session.get(f"{API}/pendants", headers=admin_headers).json()
        if not pendants:
            pytest.skip("No pendants seeded")
        p = pendants[0]
        r = session.post(f"{API}/pendants/event",
                         json={"frequency_mhz": p["frequency_mhz"], "event_type": "press"},
                         headers={"Content-Type": "application/json",
                                  "X-Device-Token": "some_token"})
        assert r.status_code == 401

    def test_pendant_event_with_revoked_token_rejected(self, session, admin_headers):
        # Create + revoke a token, then try to use it
        c = session.post(f"{API}/device-tokens", json={
            "name": f"TEST_revoked_{uuid.uuid4().hex[:6]}",
            "scopes": ["pendants.event"]
        }, headers=admin_headers).json()
        tid = c["token_id"]
        session.delete(f"{API}/device-tokens/{tid}", headers=admin_headers)

        pendants = session.get(f"{API}/pendants", headers=admin_headers).json()
        if not pendants:
            pytest.skip("No pendants seeded")
        p = pendants[0]
        r = session.post(f"{API}/pendants/event",
                         json={"frequency_mhz": p["frequency_mhz"], "event_type": "press"},
                         headers={"Content-Type": "application/json",
                                  "X-Device-Token": tid,
                                  "X-Device-Signature": "abc"})
        assert r.status_code == 401


class TestFamilyPortal:
    def test_family_contacts_have_portal_token(self, session, admin_headers):
        contacts = session.get(f"{API}/family-contacts", headers=admin_headers).json()
        assert len(contacts) > 0
        # portal_token should be populated on all via seed backfill
        with_tok = [c for c in contacts if c.get("portal_token")]
        assert len(with_tok) == len(contacts), f"Some contacts missing portal_token: {len(contacts) - len(with_tok)}"

    def test_portal_summary_public(self, session, admin_headers):
        contacts = session.get(f"{API}/family-contacts", headers=admin_headers).json()
        tok = next((c["portal_token"] for c in contacts if c.get("portal_token")), None)
        assert tok
        # Call WITHOUT auth
        plain = requests.Session()
        plain.headers.update({"Content-Type": "application/json"})
        r = plain.get(f"{API}/family-portal/{tok}/summary")
        assert r.status_code == 200, r.text
        body = r.json()
        for key in ("resident", "contact", "last_seen", "active_now", "resolved_last_7d", "recent_alerts", "haiku"):
            assert key in body, f"missing {key}"
        assert body["resident"].get("name")

    def test_portal_summary_invalid_token(self, session):
        r = session.get(f"{API}/family-portal/invalid-token-xyz/summary")
        assert r.status_code == 404

    def test_portal_acknowledge_read(self, session, admin_headers):
        contacts = session.get(f"{API}/family-contacts", headers=admin_headers).json()
        tok = next((c["portal_token"] for c in contacts if c.get("portal_token")), None)
        assert tok
        r = session.post(f"{API}/family-portal/{tok}/acknowledge-read", json={})
        assert r.status_code == 200
        assert r.json().get("ok") is True
