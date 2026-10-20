"""Synthetic profile-only request discovery; no providers or live records."""
import json

import pytest
from pymongo.errors import ExecutionTimeout

from tests.test_dot_aria_channel import (
    DEPT, OTHER, RESIDENT, ROOM, TAG, create_request, db, request, run, setup,
)
from routes import resident_request_lookup as lookup

CREATED = "2026-10-20T07:42:06+00:00"
UPDATED = "2026-10-20T08:00:00+00:00"


def seed(suffix="sink", **fields):
    task = {
        "task_id": f"{TAG}_{suffix}", "resident_id": RESIDENT, "room": ROOM,
        "source": "dot_aria", "category": DEPT, "visibility_role": DEPT,
        "title": "Sink leaking", "description": "Sink leaking",
        "status": "pending", "created_at": CREATED, **fields,
    }
    run(db.staff_tasks.insert_one(task))
    return task["task_id"]


def find(**body):
    return run(request("POST", "/api/dot-aria/requests/find", json=body))


@pytest.fixture(autouse=True)
def clean_notification_fixtures():
    yield
    run(db.notifications.delete_many({"related_object_id": {"$regex": f"^{TAG}_"}}))


def test_lookup_finds_sink_without_id_and_preserves_recorded_clock(monkeypatch):
    async def zone():
        return "America/Chicago"
    monkeypatch.setattr(lookup, "facility_tz", zone)
    task_id = seed(event_log=[{"at": UPDATED, "field": "note", "text": "PRIVATE STAFF NOTE"}])
    result = find(department=DEPT, issue="LEAKING sink").json()
    assert result["found"] is True and len(result["requests"]) == 1
    row = result["requests"][0]
    assert row["request_id"] == task_id and row["summary"] == "Sink leaking"
    assert row["department"] == {"slug": DEPT, "label": "Test Maintenance"}
    assert row["created_at"] == CREATED
    assert row["created"]["local"] == "2026-10-20T02:42:06-05:00"
    assert row["created"]["timezone"] == "America/Chicago"
    assert row["updated_at"] == UPDATED and row["updated"]["source"] == "latest_recorded_event"
    assert row["status"] == "pending" and row["lifecycle"] == "open" and row["is_open"]
    assert "PRIVATE STAFF NOTE" not in json.dumps(result)


def test_profile_scope_applies_before_filter_and_limit_and_never_falls_back_to_room():
    mine = seed("mine")
    seed("other", resident_id=OTHER, created_at="2026-10-21T00:00:00+00:00")
    seed("unbound", resident_id=None)
    seed("staff_private", source="staff", description="Internal staff planning")
    result = find(limit=1, issue="sink").json()
    assert [r["request_id"] for r in result["requests"]] == [mine]
    assert result["has_more"] is False


@pytest.mark.parametrize("field,value", [
    ("resident_id", OTHER), ("room", "215"), ("person_or_room", "Someone else"),
    ("request_id", "arbitrary"), ("limit", 21), ("limit", 0), ("limit", True),
    ("offset", -1), ("offset", 1001), ("scope", "global"), ("issue", " "),
    ("department", {"$ne": None}), ("issue", "x" * 121),
])
def test_unknown_scope_and_unbounded_inputs_are_rejected(field, value):
    assert find(**{field: value}).status_code == 422


def test_lookup_requires_same_source_token_owner_and_fresh_profile_binding(monkeypatch):
    path = "/api/dot-aria/requests/find"
    assert run(request("POST", path, json={}, token="wrong")).status_code == 401
    assert run(request("POST", path, json={}, client_ip="192.168.122.99")).status_code == 403
    run(db.residents.update_one({"resident_id": RESIDENT}, {"$set": {"room": "214-HOME"}}))
    assert find().status_code == 503
    run(db.kiosks.insert_one({"kiosk_id": f"{TAG}_pin", "room": ROOM, "resident_id": RESIDENT}))
    try:
        assert find().status_code == 200
        run(db.kiosks.update_one({"kiosk_id": f"{TAG}_pin"}, {"$set": {"resident_id": OTHER}}))
        assert find().status_code == 503
    finally:
        run(db.kiosks.delete_one({"kiosk_id": f"{TAG}_pin"}))
    monkeypatch.delenv("CAOSCARE_DOT_ARIA_TOKEN_SHA256")
    assert find().status_code == 503


def test_recent_includes_closed_history_and_open_excludes_it():
    opened = seed("open")
    closed = seed("closed", status="completed", completed_at=UPDATED)
    recent = find().json()["requests"]
    assert {r["request_id"] for r in recent} == {opened, closed}
    finished = next(r for r in recent if r["request_id"] == closed)
    assert finished["lifecycle"] == "resolved" and finished["is_open"] is False
    assert [r["request_id"] for r in find(scope="open").json()["requests"]] == [opened]
    exact = run(request("POST", "/api/dot-aria/requests/status", json={"request_id": closed})).json()
    assert exact["request"]["found"] and exact["request"]["status"] == "completed"


def test_multiple_issues_and_pages_do_not_collapse_or_hide_matches():
    ids = [seed(f"sink{i}", description=f"Sink {i} leaking") for i in range(4)]
    seed("lamp", title="Lamp", description="Broken lamp")
    first = find(issue="sink", limit=2).json()
    second = find(issue="sink", limit=2, offset=first["next_offset"]).json()
    assert first["has_more"] and first["next_offset"] == 2
    assert not second["has_more"] and second["next_offset"] is None
    rows = first["requests"] + second["requests"]
    assert {r["request_id"] for r in rows} == set(ids)
    assert len({r["summary"] for r in rows}) == 4
    assert first["coverage"]["snapshot"] is False


def test_filter_precedes_pagination_and_regex_is_literal():
    mine = seed("older_sink", created_at="2026-09-01T00:00:00+00:00")
    seed("new_lamp", title="Lamp", description="Broken lamp")
    assert find(issue="sink", limit=1).json()["requests"][0]["request_id"] == mine
    empty = find(issue=".*").json()
    assert empty["found"] is False and empty["requests"] == []
    assert "not proof no request exists" in empty["message"]
    assert empty["coverage"]["time_window"] == "retained_records_no_age_cutoff"
    assert find(department="another_department").json()["found"] is False


def test_pagination_cap_reports_incomplete_coverage(monkeypatch):
    seed("a")
    seed("b")
    monkeypatch.setattr(lookup, "MAX_OFFSET", 0)
    result = find(limit=1).json()
    assert result["has_more"] and result["pagination_limit_reached"]
    assert result["next_offset"] is None
    assert "not an exhaustive account history" in result["message"]


@pytest.mark.parametrize("stamp", [None, "not-a-time", "2026-10-20T07:42:06"])
def test_missing_invalid_or_timezone_unknown_timestamps_are_not_invented(stamp):
    seed(created_at=stamp, event_log=[])
    row = find().json()["requests"][0]
    assert row["created_at"] is None and row["created"] is None
    assert row["updated_at"] is None and row["updated"] is None


@pytest.mark.parametrize("status,expected,reached", [
    ("delivered", "delivered", True), ("sent", "sent", True),
    ("logged", "not_sent", False), ("failed", "failed", False),
    ("simulated", "simulated", False),
])
def test_notification_result_is_real_safe_evidence(status, expected, reached):
    task_id = seed()
    run(db.notifications.insert_one({
        "related_object_type": "task", "related_object_id": task_id,
        "status": status, "to": "PRIVATE@example.invalid", "route": "PRIVATE-ROUTE",
    }))
    result = find().json()
    delivery = result["requests"][0]["delivery"]
    assert delivery["state"] == expected and delivery["reached"] is reached
    assert delivery["attempts"] == 1
    assert set(delivery) == {"state", "label", "reached", "attempts"}
    assert "PRIVATE" not in json.dumps(result)


def test_absent_notification_is_not_a_notification_claim():
    seed()
    delivery = find().json()["requests"][0]["delivery"]
    assert delivery["state"] == "none" and not delivery["reached"]
    assert delivery["attempts"] == 0


def test_repeated_discovery_is_read_only_and_preserves_retry_protection():
    created = create_request("Sink leaking", f"{TAG}:lookup-retry").json()
    task_id = created["task_id"]
    before = run(db.staff_tasks.find_one({"task_id": task_id}))
    receipts = run(db.receipts.count_documents({"related_object_id": task_id}))
    for _ in range(2):
        assert find(issue="sink").json()["requests"][0]["request_id"] == task_id
    after = run(db.staff_tasks.find_one({"task_id": task_id}))
    assert before == after
    assert run(db.receipts.count_documents({"related_object_id": task_id})) == receipts
    replay = create_request("Sink leaking", f"{TAG}:lookup-retry").json()
    assert replay["idempotent_replay"] and replay["task_id"] == task_id
    assert replay["receipt_id"] == created["receipt_id"]


def test_database_failure_is_not_returned_as_no_matching_request(monkeypatch):
    async def unavailable(*args, **kwargs):
        raise ExecutionTimeout("synthetic unavailable query")
    monkeypatch.setattr(lookup, "delivery_for", unavailable)
    seed()
    with pytest.raises(ExecutionTimeout):
        find()
