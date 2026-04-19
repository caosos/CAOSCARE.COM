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
