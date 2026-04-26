"""Iteration 10 backend tests — Realtime session config + public alert status + regressions."""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://elderly-care-voice.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

OWNER = {"email": "owner@caoscare.com", "password": "owner1234"}
ADMIN = {"email": "admin@caoscare.com", "password": "admin1234"}
STAFF = {"email": "nurse@caoscare.com", "password": "nurse1234"}


# ----- fixtures -----
@pytest.fixture(scope="module")
def s():
    sess = requests.Session()
    sess.headers.update({"Content-Type": "application/json"})
    return sess


def _admin_login(sess, creds):
    r = sess.post(f"{API}/auth/admin-login", json=creds, timeout=15)
    return r


@pytest.fixture(scope="module")
def admin_token(s):
    r = _admin_login(s, ADMIN)
    if r.status_code != 200:
        pytest.skip(f"admin login failed {r.status_code}: {r.text[:200]}")
    return r.json().get("access_token") or r.json().get("token")


@pytest.fixture(scope="module")
def admin_client(admin_token):
    sess = requests.Session()
    sess.headers.update({"Content-Type": "application/json", "Authorization": f"Bearer {admin_token}"})
    return sess


@pytest.fixture(scope="module")
def seeded_resident(admin_client):
    r = admin_client.get(f"{API}/residents", timeout=15)
    if r.status_code != 200 or not r.json():
        pytest.skip("no residents seeded")
    residents = r.json()
    # Find one with memories preferred, else first
    chosen = residents[0]
    return chosen


# ----- Auth regressions -----
class TestAuthRegressions:
    def test_owner_admin_login(self, s):
        r = _admin_login(s, OWNER)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body.get("user", {}).get("role") == "owner"

    def test_admin_admin_login(self, s):
        r = _admin_login(s, ADMIN)
        assert r.status_code == 200, r.text
        assert r.json().get("user", {}).get("role") == "admin"

    def test_staff_login(self, s):
        # staff uses /auth/login per credentials.md
        r = s.post(f"{API}/auth/login", json=STAFF, timeout=15)
        assert r.status_code == 200, r.text
        assert r.json().get("user", {}).get("role") == "staff"


# ----- Realtime session -----
class TestRealtimeSession:
    REQ_TOOLS = {"adjust_room_temperature", "toggle_light", "toggle_tv", "call_for_help", "mark_resting"}

    def test_session_default(self, s):
        r = s.post(f"{API}/realtime/session", json={}, timeout=30)
        assert r.status_code == 200, r.text
        body = r.json()
        assert "_caos" in body, "missing _caos blob"
        caos = body["_caos"]

        # Voice default
        assert caos["voice"] == "shimmer"
        # Tools
        assert "tools" in caos and isinstance(caos["tools"], list)
        names = {t.get("name") for t in caos["tools"]}
        assert names == self.REQ_TOOLS, f"tools mismatch: {names}"
        # tool_choice
        assert caos.get("tool_choice") == "auto"
        # turn_detection
        td = caos.get("turn_detection") or {}
        assert td.get("silence_duration_ms") == 1000, td
        assert td.get("type") == "server_vad"
        # temperature
        assert caos.get("temperature") == 0.6
        # instructions
        instr = caos.get("instructions") or ""
        assert "Truth discipline" in instr, "missing anti-hallucination 'Truth discipline'"
        assert "CALL THE MATCHING TOOL" in instr, "missing 'CALL THE MATCHING TOOL'"
        # context
        ctx = caos.get("context") or {}
        assert "resident_id" in ctx and "kiosk_id" in ctx and "room" in ctx
        assert ctx["resident_id"] is None  # echoed back
        # client_secret usable for WebRTC
        cs = body.get("client_secret") or {}
        assert isinstance(cs, dict) and cs.get("value"), "missing client_secret.value ephemeral key"
        assert isinstance(cs["value"], str) and len(cs["value"]) > 10

    def test_session_with_resident_with_memories(self, s, seeded_resident, admin_client):
        rid = seeded_resident["resident_id"]
        # Try to find a resident with memories
        residents_r = admin_client.get(f"{API}/residents", timeout=15)
        residents = residents_r.json()
        chosen = None
        for res in residents:
            mr = admin_client.get(f"{API}/memory/{res['resident_id']}", timeout=15)
            if mr.status_code == 200:
                data = mr.json()
                if isinstance(data, dict):
                    facts = data.get("facts") or []
                    events = data.get("events") or []
                    if facts or events:
                        chosen = res
                        break
                elif isinstance(data, list) and data:
                    chosen = res
                    break
        if not chosen:
            pytest.skip("no resident with memories found; covered by fallback test")

        r = s.post(f"{API}/realtime/session", json={
            "resident_id": chosen["resident_id"],
            "kiosk_id": "k_test",
            "room": chosen.get("room") or "101",
        }, timeout=30)
        assert r.status_code == 200, r.text
        instr = r.json()["_caos"]["instructions"]
        name = (chosen.get("preferred_name") or chosen.get("name", "").split(" ")[0]).strip()
        assert name and name in instr
        assert f"Their name is {name}. ALWAYS call them {name}" in instr, "missing strict name discipline"
        assert (f"What you know about {name} (durable facts)" in instr), "missing facts header"
        # Either bullet facts present or fallback (No facts on file yet) — for resident with memories, expect bullets
        assert (f"Recent moments with {name}" in instr)
        # context echo
        ctx = r.json()["_caos"]["context"]
        assert ctx["resident_id"] == chosen["resident_id"]
        assert ctx["kiosk_id"] == "k_test"

    def test_session_with_resident_no_memories(self, s, admin_client):
        # Find resident with NO memories (or use any seeded one's name and verify fallback text)
        residents_r = admin_client.get(f"{API}/residents", timeout=15)
        residents = residents_r.json()
        chosen = None
        for res in residents:
            mr = admin_client.get(f"{API}/memory/{res['resident_id']}", timeout=15)
            if mr.status_code == 200:
                data = mr.json()
                facts = (data.get("facts") if isinstance(data, dict) else data) or []
                events = (data.get("events") if isinstance(data, dict) else []) or []
                if not facts and not events:
                    chosen = res
                    break
        if not chosen:
            # As a fallback create a synthetic resident_id that doesn't exist — instructions
            # will return the persona without bins; not what we want. Skip cleanly.
            pytest.skip("no resident without memories available")

        r = s.post(f"{API}/realtime/session", json={"resident_id": chosen["resident_id"]}, timeout=30)
        assert r.status_code == 200, r.text
        instr = r.json()["_caos"]["instructions"]
        # Fallback text must appear
        assert "No facts on file yet" in instr, "missing no-facts fallback"
        assert "No prior moments on file" in instr, "missing no-events fallback"


# ----- Public alert status (kiosk polling) -----
class TestPublicAlertStatus:
    def test_404_unknown(self, s):
        r = s.get(f"{API}/alerts/public/does_not_exist_xyz/status", timeout=15)
        assert r.status_code == 404

    def test_full_lifecycle(self, s, admin_client, seeded_resident):
        # CREATE via public endpoint with ai_triage
        rid = seeded_resident["resident_id"]
        room = seeded_resident.get("room")
        payload = {
            "resident_id": rid,
            "room": room,
            "severity": "assist",
            "message": "TEST_iter10 ai_triage call",
            "triggered_by": "ai_triage",
        }
        r = s.post(f"{API}/alerts", json=payload, timeout=15)
        assert r.status_code in (200, 201), r.text
        alert = r.json()
        alert_id = alert["alert_id"]
        assert alert.get("triggered_by") == "ai_triage"

        # PUBLIC status active
        pub = s.get(f"{API}/alerts/public/{alert_id}/status", timeout=15)
        assert pub.status_code == 200, pub.text
        body = pub.json()
        assert set(body.keys()) == {"alert_id", "status", "severity"}, f"unexpected keys: {body.keys()}"
        assert body["status"] == "active"
        assert body["severity"] == "assist"
        # PII MUST NOT leak
        for forbidden in ("resident_id", "room", "message", "resident_name", "kiosk_id", "zone"):
            assert forbidden not in body

        # AUTHED legacy GET requires auth
        no_auth = s.get(f"{API}/alerts/{alert_id}", timeout=15)
        assert no_auth.status_code in (401, 403), no_auth.status_code
        with_auth = admin_client.get(f"{API}/alerts/{alert_id}", timeout=15)
        assert with_auth.status_code == 200, with_auth.text

        # RESOLVE via authed
        rv = admin_client.post(f"{API}/alerts/{alert_id}/resolve", timeout=15)
        assert rv.status_code == 200, rv.text

        # PUBLIC status now resolved
        pub2 = s.get(f"{API}/alerts/public/{alert_id}/status", timeout=15)
        assert pub2.status_code == 200
        assert pub2.json()["status"] == "resolved"


# ----- Public room device command -----
class TestPublicRoomCommand:
    def test_endpoint_reachable_no_auth_temperature(self, s, seeded_resident):
        room = seeded_resident.get("room") or "101"
        # action enum: power, brightness, temperature, fan_speed, volume, channel, color, position
        r = s.post(
            f"{API}/devices/public/room/{room}/command",
            json={"action": "temperature", "value": 72},
            timeout=15,
        )
        # Endpoint may 404 if no device, 400 if no matching capability, 200 if accepted.
        # Crucially must NOT be 401/403.
        assert r.status_code not in (401, 403), f"unexpected auth challenge: {r.status_code} {r.text[:200]}"
        assert r.status_code in (200, 400, 404), r.text

    def test_power_on(self, s, seeded_resident):
        room = seeded_resident.get("room") or "101"
        r = s.post(
            f"{API}/devices/public/room/{room}/command",
            json={"action": "power", "value": "on"},
            timeout=15,
        )
        assert r.status_code not in (401, 403)
        assert r.status_code in (200, 400, 404)

    def test_volume(self, s, seeded_resident):
        room = seeded_resident.get("room") or "101"
        r = s.post(
            f"{API}/devices/public/room/{room}/command",
            json={"action": "volume", "value": 30},
            timeout=15,
        )
        assert r.status_code not in (401, 403)
        assert r.status_code in (200, 400, 404)


# ----- Admin endpoint regressions -----
class TestAdminRegressions:
    def test_residents_list(self, admin_client):
        r = admin_client.get(f"{API}/residents", timeout=15)
        assert r.status_code == 200, r.text
        assert isinstance(r.json(), list)

    def test_alerts_feed(self, admin_client):
        r = admin_client.get(f"{API}/alerts/feed", timeout=15)
        assert r.status_code == 200, r.text
        assert isinstance(r.json(), list)

    def test_alerts_stats(self, admin_client):
        r = admin_client.get(f"{API}/alerts/stats", timeout=15)
        assert r.status_code == 200, r.text
        body = r.json()
        for k in ("active", "acknowledged", "resolved_24h", "emergency_active"):
            assert k in body
