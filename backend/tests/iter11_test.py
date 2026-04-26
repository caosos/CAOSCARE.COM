"""Iteration 11 backend tests — Research (Perplexity+Claude fallback), Weather (Open-Meteo),
Timers (public+authed), and Realtime session 9-tool surface + time-anchor + storyteller block."""
import os
import time
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://elderly-care-voice.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

OWNER = {"email": "owner@caoscare.com", "password": "owner1234"}
ADMIN = {"email": "admin@caoscare.com", "password": "admin1234"}
STAFF = {"email": "nurse@caoscare.com", "password": "nurse1234"}


# ---------- fixtures ----------
@pytest.fixture(scope="module")
def s():
    sess = requests.Session()
    sess.headers.update({"Content-Type": "application/json"})
    return sess


@pytest.fixture(scope="module")
def admin_token(s):
    r = s.post(f"{API}/auth/admin-login", json=ADMIN, timeout=15)
    if r.status_code != 200:
        pytest.skip(f"admin login failed: {r.status_code} {r.text[:200]}")
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
    return r.json()[0]


# ---------- Research (Claude fallback because PERPLEXITY_API_KEY is empty) ----------
class TestResearch:
    def test_research_haiku_uses_claude_fallback(self, s):
        r = s.post(f"{API}/research", json={"question": "what is a haiku"}, timeout=60)
        assert r.status_code == 200, r.text
        body = r.json()
        # Required fields
        assert "answer" in body and "citations" in body and "source" in body
        assert isinstance(body["citations"], list)
        # PERPLEXITY_API_KEY empty -> must be claude (or "none" if Emergent key fails)
        assert body["source"] == "claude", f"expected source=claude, got {body['source']} (full: {body})"
        # Non-empty answer
        assert isinstance(body["answer"], str) and len(body["answer"].strip()) > 10, body

    def test_research_empty_question_rejected(self, s):
        r = s.post(f"{API}/research", json={"question": ""}, timeout=15)
        # Pydantic min_length=2 -> 422; explicit empty check could also yield 400
        assert r.status_code in (400, 422), f"expected 400/422, got {r.status_code} {r.text[:200]}"

    def test_research_short_question_rejected(self, s):
        # min_length=2 -> single-char should fail
        r = s.post(f"{API}/research", json={"question": "a"}, timeout=15)
        assert r.status_code in (400, 422)


# ---------- Weather (Open-Meteo, no key) ----------
class TestWeather:
    REQUIRED_KEYS = {"label", "temperature_f", "feels_like_f", "condition", "high_f", "low_f", "chance_of_rain", "narrative"}

    def test_default_facility_weather(self, s):
        r = s.get(f"{API}/weather/current", timeout=20)
        assert r.status_code == 200, r.text
        body = r.json()
        # Schema completeness
        missing = self.REQUIRED_KEYS - set(body.keys())
        assert not missing, f"missing keys: {missing}"
        # Default label from .env
        assert body["label"] == "Lancaster, PA", body["label"]
        # Narrative is a single human sentence ending with a period
        narrative = body["narrative"]
        assert isinstance(narrative, str) and narrative.strip().endswith("."), narrative
        # Temperature reasonable
        assert isinstance(body["temperature_f"], (int, float))
        assert -50 <= body["temperature_f"] <= 130

    def test_override_location_boston(self, s):
        r = s.get(f"{API}/weather/current", params={"lat": 42.36, "lon": -71.06, "label": "Boston"}, timeout=20)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["label"] == "Boston"
        assert "Boston" in body["narrative"], body["narrative"]
        assert body["narrative"].strip().endswith(".")


# ---------- Timers ----------
class TestTimers:
    def test_create_public_timer_validation_min(self, s):
        r = s.post(f"{API}/timers/public", json={"label": "TEST_iter11 zero", "minutes": 0, "room": "TEST_room"}, timeout=15)
        assert r.status_code in (400, 422), f"expected validation error, got {r.status_code}"

    def test_create_public_timer_validation_max(self, s):
        r = s.post(f"{API}/timers/public", json={"label": "TEST_iter11 huge", "minutes": 1000, "room": "TEST_room"}, timeout=15)
        assert r.status_code in (400, 422)

    def test_one_shot_fire_and_mark_flow(self, s):
        room = "TEST_iter11_room"
        # Create due in 0.1 min = 6 seconds
        r = s.post(
            f"{API}/timers/public",
            json={"label": "TEST_iter11 take pills", "minutes": 0.1, "room": room},
            timeout=15,
        )
        assert r.status_code in (200, 201), r.text
        timer = r.json()
        # Schema
        assert "timer_id" in timer and timer["timer_id"]
        assert "due_at" in timer and timer["due_at"]
        assert timer.get("fired") is False
        assert timer.get("room") == room
        timer_id = timer["timer_id"]

        # Wait for it to be due
        time.sleep(7)

        # Poll due-by-room — should return our timer
        due = s.get(f"{API}/timers/due/by-room/{room}", timeout=15)
        assert due.status_code == 200, due.text
        ids = [t["timer_id"] for t in due.json()]
        assert timer_id in ids, f"timer {timer_id} not in due list: {due.json()}"

        # Re-poll — should now be empty (fired/marked)
        due2 = s.get(f"{API}/timers/due/by-room/{room}", timeout=15)
        assert due2.status_code == 200
        ids2 = [t["timer_id"] for t in due2.json()]
        assert timer_id not in ids2, f"timer {timer_id} still in re-poll: {due2.json()}"

    def test_authed_list_and_delete(self, s, admin_client):
        # Create a timer to delete
        r = s.post(f"{API}/timers/public", json={"label": "TEST_iter11 todelete", "minutes": 60, "room": "TEST_iter11_del"}, timeout=15)
        assert r.status_code in (200, 201)
        tid = r.json()["timer_id"]

        # Listing requires auth
        no_auth = s.get(f"{API}/timers", timeout=15)
        assert no_auth.status_code in (401, 403), no_auth.status_code

        listing = admin_client.get(f"{API}/timers", timeout=15)
        assert listing.status_code == 200, listing.text
        assert isinstance(listing.json(), list)
        assert any(t.get("timer_id") == tid for t in listing.json())

        # Delete unauthed must fail
        no_auth_del = s.delete(f"{API}/timers/{tid}", timeout=15)
        assert no_auth_del.status_code in (401, 403)

        # Delete with auth succeeds
        d = admin_client.delete(f"{API}/timers/{tid}", timeout=15)
        assert d.status_code == 200, d.text

        # 404 for unknown
        d2 = admin_client.delete(f"{API}/timers/does_not_exist_xyz", timeout=15)
        assert d2.status_code == 404


# ---------- Realtime session — 9 tools + time anchor + storyteller block ----------
class TestRealtimeSession:
    REQ_TOOLS = {
        "adjust_room_temperature", "toggle_light", "toggle_tv", "call_for_help",
        "mark_resting", "get_current_time", "get_weather", "research_topic", "set_timer",
    }

    def test_session_has_nine_tools_and_anchors(self, s):
        r = s.post(f"{API}/realtime/session", json={}, timeout=30)
        assert r.status_code == 200, r.text
        body = r.json()
        assert "_caos" in body
        caos = body["_caos"]

        # Exactly 9 tools, names match
        tools = caos.get("tools") or []
        names = {t.get("name") for t in tools}
        assert len(tools) == 9, f"expected 9 tools, got {len(tools)}: {names}"
        assert names == self.REQ_TOOLS, f"tool names mismatch: {names ^ self.REQ_TOOLS}"

        # Instructions
        instr = caos.get("instructions") or ""
        assert "## Right now" in instr, "missing '## Right now' time anchor"
        # Storyteller / "more than Alexa" block
        assert "more than Alexa" in instr, "missing 'more than Alexa' storyteller block"
        # Tool guidance for new tools
        assert "research_topic" in instr, "missing research_topic guidance"
        assert "get_weather" in instr, "missing get_weather guidance"
        assert "get_current_time" in instr, "missing get_current_time guidance"
        assert "set_timer" in instr, "missing set_timer guidance"
        # Time anchor mentions facility label
        assert "Lancaster, PA" in instr, "facility label missing from time anchor"

        # context blob
        ctx = caos.get("context") or {}
        assert ctx.get("facility_label") == "Lancaster, PA"
        assert ctx.get("facility_tz") == "America/New_York"

    def test_set_timer_tool_schema(self, s):
        r = s.post(f"{API}/realtime/session", json={}, timeout=30)
        assert r.status_code == 200
        tools = {t["name"]: t for t in r.json()["_caos"]["tools"]}
        st = tools["set_timer"]
        params = st["parameters"]
        assert params.get("additionalProperties") is False
        props = params["properties"]
        assert props["minutes"]["minimum"] == 0.1
        assert props["minutes"]["maximum"] == 720
        assert "label" in props
        assert set(params["required"]) == {"minutes", "label"}


# ---------- Backend regressions ----------
class TestRegressions:
    def test_owner_admin_login(self, s):
        r = s.post(f"{API}/auth/admin-login", json=OWNER, timeout=15)
        assert r.status_code == 200, r.text
        assert r.json().get("user", {}).get("role") == "owner"

    def test_admin_admin_login(self, s):
        r = s.post(f"{API}/auth/admin-login", json=ADMIN, timeout=15)
        assert r.status_code == 200, r.text
        assert r.json().get("user", {}).get("role") == "admin"

    def test_staff_login(self, s):
        r = s.post(f"{API}/auth/login", json=STAFF, timeout=15)
        assert r.status_code == 200, r.text
        assert r.json().get("user", {}).get("role") == "staff"

    def test_residents(self, admin_client):
        r = admin_client.get(f"{API}/residents", timeout=15)
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_alerts_feed(self, admin_client):
        r = admin_client.get(f"{API}/alerts/feed", timeout=15)
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_alerts_stats(self, admin_client):
        r = admin_client.get(f"{API}/alerts/stats", timeout=15)
        assert r.status_code == 200
        body = r.json()
        for k in ("active", "acknowledged", "resolved_24h", "emergency_active"):
            assert k in body

    def test_alerts_create_kiosk(self, s, seeded_resident):
        payload = {
            "resident_id": seeded_resident["resident_id"],
            "room": seeded_resident.get("room"),
            "severity": "assist",
            "message": "TEST_iter11 regression",
            "triggered_by": "ai_triage",
        }
        r = s.post(f"{API}/alerts", json=payload, timeout=15)
        assert r.status_code in (200, 201), r.text
        alert_id = r.json()["alert_id"]
        # public status
        pub = s.get(f"{API}/alerts/public/{alert_id}/status", timeout=15)
        assert pub.status_code == 200
        assert pub.json()["status"] == "active"

    def test_devices_public_room_command(self, s, seeded_resident):
        room = seeded_resident.get("room") or "101"
        r = s.post(
            f"{API}/devices/public/room/{room}/command",
            json={"action": "temperature", "value": 72},
            timeout=15,
        )
        # Must NOT be auth-challenged
        assert r.status_code not in (401, 403), r.text
        assert r.status_code in (200, 400, 404), r.text
