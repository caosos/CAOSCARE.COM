"""Iteration 6 backend tests: haiku, paging, medications."""
import os
from datetime import datetime, timezone
import pytest
import requests

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
API = f"{BASE_URL}/api"

ADMIN = {"email": "admin@caoscare.com", "password": "admin1234"}
NURSE = {"email": "nurse@caoscare.com", "password": "nurse1234"}


def _login(creds):
    r = requests.post(f"{API}/auth/login", json=creds, timeout=20)
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture(scope="module")
def admin_token():
    return _login(ADMIN)


@pytest.fixture(scope="module")
def nurse_token():
    return _login(NURSE)


def _h(tok):
    return {"Authorization": f"Bearer {tok}"}


# ---------------- HAIKU ----------------

class TestHaiku:
    def test_generate_today_and_idempotent(self, admin_token):
        r1 = requests.post(f"{API}/haiku/generate-today", headers=_h(admin_token), timeout=180)
        assert r1.status_code == 200, r1.text
        d1 = r1.json()
        assert "created" in d1 and "skipped" in d1 and "failed" in d1 and "day" in d1
        # Second call same day should create 0 and skip all residents
        r2 = requests.post(f"{API}/haiku/generate-today", headers=_h(admin_token), timeout=60)
        assert r2.status_code == 200
        d2 = r2.json()
        assert d2["created"] == 0
        assert d2["skipped"] >= 1
        assert d2["day"] == d1["day"]

    def test_generate_today_forbidden_for_nurse(self, nurse_token):
        r = requests.post(f"{API}/haiku/generate-today", headers=_h(nurse_token), timeout=30)
        assert r.status_code == 403

    def test_latest_returns_per_resident(self, admin_token):
        r = requests.get(f"{API}/haiku/latest", headers=_h(admin_token), timeout=30)
        assert r.status_code == 200
        items = r.json()
        assert isinstance(items, list)
        assert len(items) >= 1
        for it in items:
            assert "text" in it and isinstance(it["text"], str) and len(it["text"]) > 0
            assert "resident_name" in it
            assert "resident_id" in it

    def test_routing_generate_today_not_matched_as_resident_id(self, admin_token):
        # Hitting /generate-today with GET should be 405 (path exists) or 404, NOT treated as resident_id
        # Confirm POST path works (covered above) and that /haiku/{bogus_id} returns 404 (resident not found)
        r = requests.post(f"{API}/haiku/nonexistent_resident_id", headers=_h(admin_token), timeout=15)
        assert r.status_code == 404


# ---------------- PAGING ----------------

class TestPaging:
    def test_event_public_enriches_via_capcode(self, admin_token):
        # pendant PEN-0101 maps to Margaret in room 101
        payload = {
            "source": "facility_rf",
            "cap_code": "PEN-0101",
            "message": "TEST_PAGE call bell 101",
            "urgency": "page",
        }
        r = requests.post(f"{API}/paging/event", json=payload, timeout=15)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["resident_name"] is not None
        assert d["room"] == "101"
        assert d["message"].startswith("TEST_PAGE")
        assert d["source"] == "facility_rf"

    def test_feed_readable_by_nurse_and_admin(self, nurse_token, admin_token):
        for tok in (nurse_token, admin_token):
            r = requests.get(f"{API}/paging/feed", headers=_h(tok), timeout=15)
            assert r.status_code == 200
            items = r.json()
            assert isinstance(items, list)
            # should include our TEST_PAGE we just posted
            assert any("TEST_PAGE" in (i.get("message") or "") for i in items)
            # sorted desc
            if len(items) >= 2:
                assert items[0]["created_at"] >= items[1]["created_at"]

    def test_feed_requires_auth(self):
        r = requests.get(f"{API}/paging/feed", timeout=15)
        assert r.status_code in (401, 403)

    def test_simulate_admin_only(self, admin_token, nurse_token):
        payload = {"source": "sim", "message": "TEST_SIM page", "urgency": "stat"}
        r = requests.post(f"{API}/paging/simulate", json=payload, headers=_h(nurse_token), timeout=15)
        assert r.status_code == 403

        r2 = requests.post(f"{API}/paging/simulate", json=payload, headers=_h(admin_token), timeout=15)
        assert r2.status_code == 200
        d = r2.json()
        assert d["source"] == "sim"
        assert d["message"] == "TEST_SIM page"


# ---------------- MEDICATIONS ----------------

class TestMedications:
    def test_list_seeded(self, admin_token):
        r = requests.get(f"{API}/medications", headers=_h(admin_token), timeout=15)
        assert r.status_code == 200
        items = r.json()
        assert isinstance(items, list)
        assert len(items) >= 4  # seed created 4

    def test_create_delete_denormalized(self, admin_token):
        # pick a resident
        rr = requests.get(f"{API}/residents", headers=_h(admin_token), timeout=15)
        assert rr.status_code == 200
        residents = rr.json()
        target = next((x for x in residents if x.get("room") == "101"), residents[0])

        payload = {
            "resident_id": target["resident_id"],
            "title": "TEST_MED evening pill",
            "time_hhmm": "21:00",
            "days": ["mon", "tue", "wed", "thu", "fri", "sat", "sun"],
            "dose_notes": "TEST notes",
            "active": True,
        }
        c = requests.post(f"{API}/medications", json=payload, headers=_h(admin_token), timeout=15)
        assert c.status_code == 200, c.text
        d = c.json()
        assert d["resident_name"] == target["name"]
        assert d["room"] == target.get("room")
        assert d["title"] == "TEST_MED evening pill"
        rid = d["reminder_id"]

        # cleanup
        dl = requests.delete(f"{API}/medications/{rid}", headers=_h(admin_token), timeout=15)
        assert dl.status_code == 200

        # 404 second time
        dl2 = requests.delete(f"{API}/medications/{rid}", headers=_h(admin_token), timeout=15)
        assert dl2.status_code == 404

    def test_due_by_room_public_then_ack(self, admin_token):
        """Create a reminder for current UTC minute in room 101, confirm public
        /due/by-room/101 returns it, ack, then confirm it's filtered out."""
        # Find resident in room 101
        rr = requests.get(f"{API}/residents", headers=_h(admin_token), timeout=15)
        target = next(x for x in rr.json() if x.get("room") == "101")

        now = datetime.now(timezone.utc)
        hhmm = now.strftime("%H:%M")
        day_short = now.strftime("%a").lower()[:3]

        payload = {
            "resident_id": target["resident_id"],
            "title": "TEST_MED_DUE now",
            "time_hhmm": hhmm,
            "days": [day_short],
            "dose_notes": "n/a",
            "active": True,
        }
        c = requests.post(f"{API}/medications", json=payload, headers=_h(admin_token), timeout=15)
        assert c.status_code == 200, c.text
        rid = c.json()["reminder_id"]

        try:
            # PUBLIC - no auth
            due = requests.get(f"{API}/medications/due/by-room/101", timeout=15)
            assert due.status_code == 200
            items = due.json()
            assert any(i.get("reminder_id") == rid for i in items), f"Expected reminder in due list: {items}"

            # ACK (public)
            ack = requests.post(f"{API}/medications/ack/{rid}", timeout=15)
            assert ack.status_code == 200

            # Second fetch should exclude the acked reminder
            due2 = requests.get(f"{API}/medications/due/by-room/101", timeout=15)
            assert due2.status_code == 200
            items2 = due2.json()
            assert not any(i.get("reminder_id") == rid for i in items2)
        finally:
            requests.delete(f"{API}/medications/{rid}", headers=_h(admin_token), timeout=15)

    def test_due_by_room_public_no_auth_required(self):
        r = requests.get(f"{API}/medications/due/by-room/101", timeout=15)
        assert r.status_code == 200
