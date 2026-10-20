"""Default-off Dot Aria channel: auth, one-profile scope and real receipts."""
import asyncio
import hashlib
import os
import sys
import uuid

import httpx
import pytest
from fastapi import FastAPI

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if os.environ.get("DB_NAME") in ("caoscare", "", None):
    pytest.skip("writes test data; point DB_NAME at a scratch database", allow_module_level=True)

from deps import db  # noqa: E402
from routes import dot_aria_channel as channel  # noqa: E402
from routes import resident_requests  # noqa: E402

TAG = f"dotaria_{uuid.uuid4().hex[:8]}"
TOKEN = f"token-{TAG}"
OWNER = f"{TAG}_owner"
RESIDENT = f"{TAG}_approved_profile"
OTHER = f"{TAG}_unrelated_profile"
ROOM = "214"
DEPT = f"{TAG}_maintenance"
DATE = "2026-10-19"


def run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


async def no_notice(*args, **kwargs):
    return None


@pytest.fixture(autouse=True)
def setup(monkeypatch):
    monkeypatch.setenv("CAOSCARE_DOT_ARIA_TOKEN_SHA256", hashlib.sha256(TOKEN.encode()).hexdigest())
    monkeypatch.setenv("CAOSCARE_DOT_ARIA_OWNER_USER_ID", OWNER)
    monkeypatch.setenv("CAOSCARE_DOT_ARIA_PROFILE_RESIDENT_ID", RESIDENT)
    monkeypatch.setenv("CAOSCARE_DOT_ARIA_ALLOWED_HOSTS", "192.168.122.137")
    monkeypatch.setattr(resident_requests, "notify_department", no_notice)
    run(db.users.insert_one({"user_id": OWNER, "name": "Michael", "email": f"{OWNER}@x.test", "role": "owner"}))
    run(db.residents.insert_many([
        {"resident_id": RESIDENT, "name": f"Approved {TAG}", "preferred_name": "Approved", "room": ROOM,
         "synthetic": True},
        {"resident_id": OTHER, "name": f"Unrelated {TAG}", "preferred_name": "Unrelated",
         "room": f"{ROOM}-other", "synthetic": True},
    ]))
    run(db.departments.insert_one({"department_id": f"dept_{TAG}", "slug": DEPT, "label": "Test Maintenance",
                                   "active": True, "created_at": "2026-10-19T00:00:00+00:00"}))
    run(db.menu_items.insert_many([
        {"menu_id": f"{TAG}_menu_live", "date": DATE, "meal_period": "dinner", "item_name": "Pot roast",
         "description": "with vegetables", "status": "approved"},
        {"menu_id": f"{TAG}_menu_draft", "date": DATE, "meal_period": "dinner", "item_name": "Secret draft",
         "status": "draft"},
    ]))
    run(db.schedule_items.insert_many([
        {"schedule_id": f"{TAG}_schedule_live", "date": DATE, "time_label": "6:00 PM", "title": "Movie",
         "description": "Community room", "category": "activities", "status": "published"},
        {"schedule_id": f"{TAG}_schedule_staff", "date": DATE, "title": "Shift note", "category": "staff_hours",
         "status": "published"},
        {"schedule_id": f"{TAG}_schedule_draft", "date": DATE, "title": "Draft event", "category": "activities",
         "status": "draft"},
    ]))
    yield
    run(db.receipts.delete_many({"$or": [{"requested_by": OWNER}, {"resident_id": {"$regex": f"^{TAG}"}}]}))
    run(db.dot_aria_operations.delete_many({"_id": {"$regex": f"^{TAG}"}}))
    run(db.staff_tasks.delete_many({"resident_id": {"$in": [RESIDENT, OTHER]}}))
    run(db.schedule_items.delete_many({"schedule_id": {"$regex": f"^{TAG}"}}))
    run(db.menu_items.delete_many({"menu_id": {"$regex": f"^{TAG}"}}))
    run(db.departments.delete_many({"slug": DEPT}))
    run(db.residents.delete_many({"resident_id": {"$in": [RESIDENT, OTHER]}}))
    run(db.users.delete_many({"user_id": OWNER}))


def app():
    application = FastAPI()
    application.include_router(channel.router, prefix="/api")
    application.include_router(resident_requests.router, prefix="/api")
    return application


async def request(method, path, *, token=TOKEN, client_ip="192.168.122.137", json=None):
    transport = httpx.ASGITransport(app=app(), client=(client_ip, 1234))
    headers = {"Authorization": f"Bearer {token}"} if token is not None else {}
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.request(method, path, headers=headers, json=json)


def create_request(summary="Fix the test lamp", operation_id=None):
    return run(request("POST", "/api/dot-aria/requests", json={
        "category": DEPT, "summary": summary, "priority": "normal",
        "operation_id": operation_id or f"{TAG}:{uuid.uuid4().hex}",
    }))


def test_channel_is_default_off_and_checks_source_credential_owner_and_profile(monkeypatch):
    monkeypatch.delenv("CAOSCARE_DOT_ARIA_TOKEN_SHA256")
    assert run(request("GET", "/api/dot-aria/capabilities")).status_code == 503
    monkeypatch.setenv("CAOSCARE_DOT_ARIA_TOKEN_SHA256", hashlib.sha256(TOKEN.encode()).hexdigest())
    assert run(request("GET", "/api/dot-aria/capabilities", client_ip="192.168.122.99")).status_code == 403
    assert run(request("GET", "/api/dot-aria/capabilities", token="wrong")).status_code == 401
    good = run(request("GET", "/api/dot-aria/capabilities"))
    assert good.status_code == 200 and good.json()["profile_scope"] == "configured_one_profile"
    assert "owner_user_id" not in good.json()
    run(db.users.delete_one({"user_id": OWNER}))
    assert run(request("GET", "/api/dot-aria/capabilities")).status_code == 503


def test_reads_return_only_published_content_and_configured_profile():
    menu = run(request("POST", "/api/dot-aria/menu", json={"date": DATE, "meal_period": "dinner"}))
    assert menu.status_code == 200 and [x["item_name"] for x in menu.json()["items"]] == ["Pot roast"]
    schedule = run(request("POST", "/api/dot-aria/schedule", json={"date": DATE}))
    assert schedule.status_code == 200 and [x["title"] for x in schedule.json()["items"]] == ["Movie"]
    profile = run(request("GET", "/api/dot-aria/profile"))
    assert profile.status_code == 200 and profile.json()["profile"]["resident_id"] == RESIDENT
    assert OTHER not in profile.text and "synthetic" not in profile.text


def test_spoken_name_room_and_unrelated_target_inputs_are_rejected():
    for body in (
        {"person_or_room": ROOM, "category": DEPT, "summary": "Fix the lamp"},
        {"resident_id": OTHER, "category": DEPT, "summary": "Fix the lamp"},
    ):
        response = run(request("POST", "/api/dot-aria/requests", json=body))
        assert response.status_code == 422
    assert run(request("POST", "/api/dot-aria/person", json={"person_or_room": ROOM})).status_code == 404
    assert run(db.staff_tasks.count_documents({"resident_id": OTHER})) == 0


def test_invalid_input_and_unavailable_backend_are_evidence_bearing(monkeypatch):
    assert run(request("POST", "/api/dot-aria/menu", json={"date": "2026-99-99"})).status_code == 422
    assert run(request("POST", "/api/dot-aria/menu", json={"meal_period": "midnight"})).status_code == 422
    assert create_request(summary="   ").status_code == 422
    invalid_department = run(request("POST", "/api/dot-aria/requests", json={
        "category": "not-a-department", "summary": "Test request", "operation_id": f"{TAG}:bad-dept",
    }))
    assert invalid_department.status_code == 400
    monkeypatch.setenv("CAOSCARE_DOT_ARIA_PROFILE_RESIDENT_ID", "missing-profile")
    unavailable = run(request("GET", "/api/dot-aria/profile"))
    assert unavailable.status_code == 503 and "unavailable" in unavailable.text


def test_write_returns_request_and_receipt_not_a_completed_service_claim():
    spoof = run(request("POST", "/api/tasks/resident-request", token=None, json={
        "category": DEPT, "resident_id": RESIDENT, "summary": "Fix the lamp", "source": "dot_aria",
    }))
    assert spoof.status_code == 403
    first = create_request()
    assert first.status_code == 200, first.text
    body = first.json()
    assert body["accepted"] is True and body["outcome"] == "request_created"
    assert body["status"] == "pending" and "does not mean service has started or completed" in body["message"]
    task = run(db.staff_tasks.find_one({"task_id": body["request_id"]}, {"_id": 0}))
    receipt = run(db.receipts.find_one({"receipt_id": body["receipt_id"]}, {"_id": 0}))
    assert task["source"] == "dot_aria" and task["resident_id"] == RESIDENT
    assert receipt["source"] == "dot_aria" and receipt["channel"] == "dot_aria"
    assert receipt["identity_basis"] == "service_credential"
    assert receipt["authority"] == "owner_delegated:home_assistant_mcp:room_214"
    assert body["task_id"] == body["request_id"]
    assert body["operation_id"] in receipt["provider_refs"]
    assert body["delivery"]["reached"] is False


def test_duplicate_delivery_is_idempotent_and_each_delivery_has_a_receipt():
    first = create_request().json()
    second = create_request("Please fix the test lamp")
    assert second.status_code == 200
    repeated = second.json()
    assert repeated["request_id"] == first["request_id"] and repeated["duplicate"] is True
    assert repeated["outcome"] == "existing_request_updated"
    assert repeated["receipt_id"] != first["receipt_id"]
    assert run(db.staff_tasks.count_documents({"resident_id": RESIDENT, "category": DEPT})) == 1


def test_same_operation_retry_returns_original_without_repeat_or_notification():
    operation_id = f"{TAG}:transport-retry"
    first = create_request(operation_id=operation_id)
    retry = create_request(operation_id=operation_id)
    assert first.status_code == retry.status_code == 200
    assert retry.json()["idempotent_replay"] is True
    assert retry.json()["request_id"] == first.json()["request_id"]
    assert retry.json()["receipt_id"] == first.json()["receipt_id"]
    task = run(db.staff_tasks.find_one({"task_id": first.json()["request_id"]}, {"_id": 0}))
    assert task["re_request_count"] == 0
    assert run(db.receipts.count_documents({"related_object_id": task["task_id"]})) == 1


def test_operation_id_conflict_rejects_changed_request_without_second_write():
    operation_id = f"{TAG}:conflict"
    first = create_request("Fix the test lamp", operation_id)
    conflict = create_request("Bring a clean towel", operation_id)
    assert first.status_code == 200 and conflict.status_code == 409
    assert run(db.staff_tasks.count_documents({"resident_id": RESIDENT})) == 1


def test_timeout_after_create_recovery_returns_committed_result():
    operation_id = f"{TAG}:caller-timeout"
    committed = create_request("Fix the timeout test lamp", operation_id).json()
    # The caller lost the first HTTP response after the server committed it.
    recovered = create_request("Fix the timeout test lamp", operation_id)
    assert recovered.status_code == 200
    assert recovered.json()["idempotent_replay"] is True
    assert recovered.json()["task_id"] == committed["task_id"]
    assert recovered.json()["receipt_id"] == committed["receipt_id"]


def test_response_preserves_truthful_notification_delivery(monkeypatch):
    async def delivered(*args, **kwargs):
        return [{"status": "delivered", "to": "test-department@example.invalid", "route": "stub"}]

    monkeypatch.setattr(resident_requests, "notify_department", delivered)
    body = create_request("Fix the delivery evidence lamp").json()
    assert body["delivery"] == {
        "state": "delivered",
        "label": "Department notified (delivery confirmed)",
        "reached": True,
        "attempts": 1,
    }
    assert "test-department@example.invalid" not in str(body)


def test_configured_profile_must_remain_in_server_bound_room_214():
    run(db.residents.update_one({"resident_id": RESIDENT}, {"$set": {"room": "215"}}))
    denied = create_request("Fix the lamp")
    assert denied.status_code == 503
    assert "Room 214" in denied.text
    assert run(db.staff_tasks.count_documents({"resident_id": RESIDENT})) == 0
    for method, path, body in (
        ("GET", "/capabilities", None), ("GET", "/departments", None),
        ("POST", "/menu", {}), ("POST", "/schedule", {}),
    ):
        assert run(request(method, "/api/dot-aria" + path, json=body)).status_code == 503


def test_exact_status_correlates_open_and_closed_request_and_denies_other_profile():
    created = create_request().json()
    request_id = created["request_id"]
    current = run(request("POST", "/api/dot-aria/requests/status", json={"request_id": request_id}))
    assert current.status_code == 200
    assert current.json()["request"]["found"] is True
    assert current.json()["request"]["task_id"] == request_id
    run(db.staff_tasks.update_one({"task_id": request_id}, {"$set": {
        "status": "resolved", "completed_at": "2026-10-19T12:00:00+00:00",
    }}))
    closed = run(request("POST", "/api/dot-aria/requests/status", json={"request_id": request_id})).json()["request"]
    assert closed["found"] is True and closed["status"] == "resolved" and closed["is_open"] is False
    run(db.staff_tasks.insert_one({
        "task_id": f"{TAG}_other_task", "title": "Private", "description": "Private", "category": DEPT,
        "priority": "normal", "status": "pending", "source": "dot_aria", "resident_id": OTHER,
        "created_at": "2026-10-19T00:00:00+00:00",
    }))
    denied = run(request("POST", "/api/dot-aria/requests/status", json={"request_id": f"{TAG}_other_task"}))
    assert denied.status_code == 200 and denied.json()["request"]["found"] is False


def test_existing_request_bus_keeps_string_delivery_and_adds_safe_evidence():
    result = run(resident_requests.create_resident_request(resident_requests.ResidentRequestInput(
        category=DEPT, summary="Fix the compatibility test lamp", resident_id=RESIDENT,
        room=ROOM, source="aria_voice",
    )))
    assert result["delivery"] == "none"
    assert result["delivery_evidence"]["reached"] is False
    assert set(result["delivery_evidence"]) == {"state", "label", "reached", "attempts"}


def test_different_issues_in_same_department_are_not_merged():
    first = create_request("Fix the broken lamp").json()
    second = create_request("Repair the leaking sink").json()
    assert first["task_id"] != second["task_id"] and second["duplicate"] is False


def test_concurrent_same_operation_has_only_one_write_and_notification(monkeypatch):
    calls = []
    async def notice(*args, **kwargs):
        calls.append(True)
        return []
    monkeypatch.setattr(resident_requests, "notify_department", notice)
    body = {"operation_id": f"{TAG}:concurrent", "category": DEPT, "summary": "Fix the concurrent lamp"}
    async def both():
        return await asyncio.gather(*(request("POST", "/api/dot-aria/requests", json=body) for _ in range(2)))
    results = run(both())
    assert all(r.status_code in (200, 409) for r in results)
    replay = run(request("POST", "/api/dot-aria/requests", json=body))
    assert replay.status_code == 200 and replay.json()["idempotent_replay"] is True
    assert len(calls) == 1 and run(db.staff_tasks.count_documents({"resident_id": RESIDENT})) == 1
