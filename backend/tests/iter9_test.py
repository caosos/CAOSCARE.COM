"""Iteration 9 tests — admin-login throttling, clinical_thresholds on residents,
wearable event threshold re-evaluation, Haiku memory extractor."""
import os
import time
import uuid
import requests
import pytest

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "admin@caoscare.com"
ADMIN_PW = "admin1234"
STAFF_EMAIL = "nurse@caoscare.com"
STAFF_PW = "nurse1234"
DOROTHY_ID = "res_d71b29751cf3"


# ---------- Fixtures ----------
@pytest.fixture(scope="module")
def s():
    sess = requests.Session()
    sess.headers.update({"Content-Type": "application/json"})
    return sess


@pytest.fixture(scope="module")
def admin_token(s):
    r = s.post(f"{API}/auth/admin-login", json={"email": ADMIN_EMAIL, "password": ADMIN_PW})
    assert r.status_code == 200, f"admin-login failed: {r.status_code} {r.text}"
    return r.json()["token"]


@pytest.fixture(scope="module")
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}


# ============ Admin-login endpoint ============
class TestAdminLogin:
    def test_admin_happy_path(self, s):
        r = s.post(f"{API}/auth/admin-login", json={"email": ADMIN_EMAIL, "password": ADMIN_PW})
        assert r.status_code == 200
        data = r.json()
        assert "token" in data and isinstance(data["token"], str) and len(data["token"]) > 20
        assert data["user"]["email"] == ADMIN_EMAIL
        assert data["user"]["role"] == "admin"

    def test_staff_creds_return_403(self, s):
        r = s.post(f"{API}/auth/admin-login", json={"email": STAFF_EMAIL, "password": STAFF_PW})
        assert r.status_code == 403
        body = r.json()
        msg = body.get("detail") or body.get("message") or ""
        assert "staff credentials" in msg.lower()

    def test_wrong_password_returns_401(self, s):
        r = s.post(f"{API}/auth/admin-login", json={"email": ADMIN_EMAIL, "password": "definitely-wrong"})
        assert r.status_code == 401

    def test_unknown_email_returns_401(self, s):
        r = s.post(f"{API}/auth/admin-login", json={"email": f"nosuch+{uuid.uuid4().hex[:6]}@caoscare.com", "password": "x"})
        assert r.status_code == 401

    def test_staff_403_does_not_increment_lockout(self, s):
        """6 staff-cred attempts should all return 403, never 429."""
        codes = []
        for _ in range(6):
            r = s.post(f"{API}/auth/admin-login", json={"email": STAFF_EMAIL, "password": STAFF_PW})
            codes.append(r.status_code)
        assert all(c == 403 for c in codes), f"staff-creds escalated to {codes}"

    def test_lockout_and_reset_on_success(self, s):
        """Use a unique admin-style email so we don't pollute the real admin bucket."""
        # We test against the real admin email but use a bad password 5x to trigger 429,
        # then a valid login should clear. Run last so other tests aren't impacted.
        bad_codes = []
        for _ in range(6):
            r = s.post(f"{API}/auth/admin-login", json={"email": ADMIN_EMAIL, "password": "wrong-xyz"})
            bad_codes.append(r.status_code)
        # Within 6 attempts, we should see at least one 429
        assert 429 in bad_codes, f"expected 429 after 5 failures, got {bad_codes}"
        # 5 failed (401), then 6th should be 429
        assert bad_codes[:5] == [401] * 5, f"expected 5x 401 then 429, got {bad_codes}"
        assert bad_codes[5] == 429

        # Now successful login must clear the throttle
        r = s.post(f"{API}/auth/admin-login", json={"email": ADMIN_EMAIL, "password": ADMIN_PW})
        assert r.status_code == 200, f"successful admin-login blocked by stale lockout: {r.status_code} {r.text}"

        # Subsequent wrong password should go back to 401 (not 429)
        r = s.post(f"{API}/auth/admin-login", json={"email": ADMIN_EMAIL, "password": "wrong-again"})
        assert r.status_code == 401, f"expected 401 after counter reset, got {r.status_code}"


# ============ Residents clinical_thresholds ============
class TestResidentClinicalThresholds:
    def test_dorothy_exists(self, s, admin_headers):
        r = s.get(f"{API}/residents/{DOROTHY_ID}", headers=admin_headers)
        assert r.status_code == 200, f"Dorothy missing: {r.text}"

    def test_set_and_clear_thresholds(self, s, admin_headers):
        # Set thresholds
        thresholds = {
            "hr_resting_min": 55,
            "hr_resting_max": 105,
            "hr_exertion_max": 135,
            "spo2_min": 92,
            "inactivity_minutes": 90,
            "notes": "TEST - chronic afib",
        }
        r = s.put(f"{API}/residents/{DOROTHY_ID}",
                  json={"name": "Dorothy Walsh", "room": "204", "pendant_id": "P-204",
                        "clinical_thresholds": thresholds},
                  headers=admin_headers)
        assert r.status_code == 200, r.text
        saved = r.json().get("clinical_thresholds") or {}
        for k, v in thresholds.items():
            assert saved.get(k) == v, f"{k}: expected {v}, got {saved.get(k)}"

        # GET persists
        r = s.get(f"{API}/residents/{DOROTHY_ID}", headers=admin_headers)
        assert r.status_code == 200
        saved = r.json().get("clinical_thresholds") or {}
        assert saved.get("hr_resting_min") == 55
        assert saved.get("hr_resting_max") == 105
        assert saved.get("hr_exertion_max") == 135

    def test_create_resident_with_thresholds(self, s, admin_headers):
        payload = {
            "name": "TEST_Threshold Person",
            "room": "T-999",
            "pendant_id": f"P-T{uuid.uuid4().hex[:6]}",
            "clinical_thresholds": {"hr_resting_min": 60, "hr_resting_max": 100,
                                     "hr_exertion_max": 140, "notes": "TEST"},
        }
        r = s.post(f"{API}/residents", json=payload, headers=admin_headers)
        assert r.status_code in (200, 201), r.text
        created = r.json()
        rid = created["resident_id"]
        assert created["clinical_thresholds"]["hr_resting_min"] == 60

        # GET verify
        g = s.get(f"{API}/residents/{rid}", headers=admin_headers)
        assert g.status_code == 200
        assert g.json()["clinical_thresholds"]["hr_exertion_max"] == 140

        # cleanup
        s.delete(f"{API}/residents/{rid}", headers=admin_headers)


# ============ Wearable event threshold re-evaluation ============
class TestWearableThresholds:
    @pytest.fixture(scope="class")
    def setup_dorothy(self, s, admin_headers):
        # Ensure Dorothy has thresholds
        thresholds = {"hr_resting_min": 55, "hr_resting_max": 105, "hr_exertion_max": 135}
        r = s.put(f"{API}/residents/{DOROTHY_ID}",
                  json={"name": "Dorothy Walsh", "room": "204", "pendant_id": "P-204",
                        "clinical_thresholds": thresholds},
                  headers=admin_headers)
        assert r.status_code == 200
        yield thresholds
        # teardown: clear thresholds per request from main agent
        s.put(f"{API}/residents/{DOROTHY_ID}",
              json={"name": "Dorothy Walsh", "room": "204", "pendant_id": "P-204",
                    "clinical_thresholds": None},
              headers=admin_headers)

    @pytest.fixture(scope="class")
    def wearable(self, s, admin_headers, setup_dorothy):
        mac = f"AA:BB:CC:{uuid.uuid4().hex[:2]}:{uuid.uuid4().hex[:2]}:{uuid.uuid4().hex[:2]}"
        r = s.post(f"{API}/wearables",
                   json={"device_label": "TEST_Dorothy Watch", "device_type": "smartwatch",
                         "mac_address": mac, "resident_id": DOROTHY_ID, "status": "active"},
                   headers=admin_headers)
        assert r.status_code in (200, 201), r.text
        w = r.json()
        yield w
        s.delete(f"{API}/wearables/{w['wearable_id']}", headers=admin_headers)

    def _post_event(self, s, wearable, event_type, heart_rate):
        # DEVICE_AUTH_REQUIRED=false in this env — no device token headers sent.
        payload = {"wearable_id": wearable["wearable_id"],
                   "event_type": event_type,
                   "heart_rate": heart_rate}
        return s.post(f"{API}/wearables/event", json=payload,
                      headers={"Content-Type": "application/json"})

    def test_suppress_hr_high_within_band(self, s, wearable):
        """HR 102 with max=105 -> heart_rate_high should be suppressed."""
        r = self._post_event(s, wearable, "heart_rate_high", 102)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body.get("alert") is None, f"alert should be suppressed: {body}"
        assert body.get("suppressed_event") == "heart_rate_high"

    def test_upgrade_periodic_ping_high(self, s, wearable):
        """HR 140 exceeds exertion_max=135 during periodic_ping -> upgrade to emergency."""
        r = self._post_event(s, wearable, "periodic_ping", 140)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body.get("alert") is not None, f"expected alert for HR 140: {body}"
        assert body["alert"]["severity"] == "emergency"
        assert "upgraded from periodic_ping" in (body["alert"].get("message") or "")

    def test_upgrade_periodic_ping_low(self, s, wearable):
        """HR 50 below min=55 during periodic_ping -> upgrade to heart_rate_low."""
        r = self._post_event(s, wearable, "periodic_ping", 50)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body.get("alert") is not None
        assert body["alert"]["severity"] == "emergency"
        assert "upgraded from periodic_ping" in (body["alert"].get("message") or "")

    def test_fall_always_alerts(self, s, wearable):
        """Fall event should ALWAYS alert regardless of HR."""
        r = self._post_event(s, wearable, "fall", 70)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body.get("alert") is not None
        assert body["alert"]["severity"] == "emergency"


# ============ Memory extractor (Haiku 4.5) ============
class TestMemoryExtraction:
    def test_extract_and_store(self, s, admin_headers):
        # pre-count
        pre = s.get(f"{API}/memory/{DOROTHY_ID}", headers=admin_headers)
        assert pre.status_code == 200
        before = len(pre.json())

        payload = {
            "resident_id": DOROTHY_ID,
            "session_id": f"test-session-{uuid.uuid4().hex[:6]}",
            "user_text": (
                "My daughter Kaitlyn visited yesterday from Boston with her twins "
                f"Emma and Lucas who just turned 7. "
                f"Marker {uuid.uuid4().hex[:8]}."
            ),
            "assistant_text": "That sounds wonderful, Dorothy. How lovely that they came to see you.",
        }
        r = s.post(f"{API}/memory/extract", json=payload, headers=admin_headers)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body.get("ok") is True
        assert "saved" in body
        assert isinstance(body["saved"], int)

        # Allow a tiny propagation delay
        time.sleep(0.5)

        post = s.get(f"{API}/memory/{DOROTHY_ID}", headers=admin_headers)
        assert post.status_code == 200
        after_items = post.json()
        assert len(after_items) >= before + body["saved"], (
            f"expected >= {before + body['saved']}, got {len(after_items)}"
        )

        # Structure sanity: saved memories must have category and importance
        if body["saved"] > 0:
            newest = sorted(after_items, key=lambda x: x.get("created_at", ""), reverse=True)[:body["saved"]]
            for m in newest:
                assert m.get("category")
                assert isinstance(m.get("importance"), int)
                assert 1 <= m["importance"] <= 5
