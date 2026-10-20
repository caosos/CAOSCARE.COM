"""Preserve the existing Room 214-HOME identity; never repin real data."""
import pytest

from tests.test_dot_aria_channel import (
    OTHER, RESIDENT, TAG, create_request, db, request, run, setup,
)


@pytest.fixture(autouse=True)
def home_pin(setup):
    run(db.residents.update_one({"resident_id": RESIDENT}, {"$set": {"room": "214-HOME"}}))
    run(db.kiosks.insert_one({
        "kiosk_id": f"{TAG}_home_pin", "room": "214", "resident_id": RESIDENT,
    }))
    yield
    run(db.kiosks.delete_many({"kiosk_id": f"{TAG}_home_pin"}))


def test_existing_pinned_home_identity_reads_and_creates_without_moving_profile():
    profile = run(request("GET", "/api/dot-aria/profile"))
    assert profile.status_code == 200
    assert profile.json()["profile"]["room"] == "214-HOME"
    assert profile.json()["profile"]["resident_id"] == RESIDENT
    created = create_request("Fix the home test lamp").json()
    assert created["accepted"] is True
    task = run(db.staff_tasks.find_one({"task_id": created["task_id"]}))
    assert task["resident_id"] == RESIDENT and task["room"] == "214"
    resident = run(db.residents.find_one({"resident_id": RESIDENT}))
    assert resident["room"] == "214-HOME"
    assert run(db.staff_tasks.count_documents({"resident_id": OTHER})) == 0


@pytest.mark.parametrize("change", [
    {"resident_id": OTHER}, {"resident_id": None}, {"room": "215"},
])
def test_home_label_without_matching_pin_denies_reads_and_writes(change):
    run(db.kiosks.update_one({"kiosk_id": f"{TAG}_home_pin"}, {"$set": change}))
    for method, path, data in (
        ("GET", "/profile", None), ("GET", "/capabilities", None),
        ("GET", "/departments", None), ("POST", "/menu", {}),
        ("POST", "/schedule", {}), ("POST", "/requests/status", {"request_id": "test-id"}),
    ):
        result = run(request(method, "/api/dot-aria" + path, json=data))
        assert result.status_code == 503 and "not pinned" in result.text
    assert create_request().status_code == 503
    assert run(db.staff_tasks.count_documents({"resident_id": RESIDENT})) == 0


def test_removed_pin_invalidates_previously_authorized_home_profile():
    assert run(request("GET", "/api/dot-aria/profile")).status_code == 200
    run(db.kiosks.delete_one({"kiosk_id": f"{TAG}_home_pin"}))
    assert run(request("GET", "/api/dot-aria/profile")).status_code == 503
    assert create_request().status_code == 503


def test_pin_does_not_authorize_a_different_room_label():
    run(db.residents.update_one({"resident_id": RESIDENT}, {"$set": {"room": "215-HOME"}}))
    assert run(request("GET", "/api/dot-aria/profile")).status_code == 503
    assert create_request().status_code == 503
