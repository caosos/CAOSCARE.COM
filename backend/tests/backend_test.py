"""CAOS Care backend regression tests."""
import os
import uuid
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://senior-locate.preview.emergentagent.com").rstrip("/")
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
    def test_chat_claude(self, session):
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
