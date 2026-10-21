from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from deps import require_admin
from routes import paid_api_call_costs as route
from routes.paid_api_call_costs import summarize_latest_calls


def mint(room, session, at, *, purpose="unknown", database="caoscare", secret=None, status=200):
    return {"kind": "session_token_minted", "session_id": session, "recorded_at": at,
            "session_secret_fp": secret, "status": status,
            "provenance": {"room": room, "run_purpose": purpose, "db_name": database}}


def test_latest_call_costs_include_complete_failed_unknown_and_no_call():
    mints = [mint("101", "s1", "2026-10-21T01:00:00Z", secret="fp1"),
             mint("102", "s2", "2026-10-21T02:00:00Z"),
             mint("103", "s3", "2026-10-21T03:00:00Z", purpose="test-gate", database="scratch")]
    docs = [
        {"kind": "session_connected", "session_secret_fp": "fp1", "billable_activity": True},
        {"kind": "provider_usage", "session_id": "s1", "billable_activity": True, "counted": True,
         "estimate": {"usd": 0.0012, "pricing_version": "p1"}},
        {"kind": "provider_usage", "session_id": "s1", "billable_activity": True, "counted": True,
         "estimate": {"usd": 0.0003, "pricing_version": "p1"}},
        {"kind": "provider_usage", "session_id": "s1", "billable_activity": True, "counted": False,
         "estimate": {"usd": 99, "pricing_version": "p1"}},
        {"kind": "session_ended", "session_id": "s1", "reason": "resident_end_call"},
        {"kind": "session_ended", "session_id": "s2", "reason": "setup_failed"},
        {"kind": "provider_request", "session_id": "s3", "billable_activity": True, "counted": True,
         "estimate": {"usd": 0.002, "pricing_version": "p1"}},
        {"kind": "provider_request", "session_id": "s3", "billable_activity": True, "counted": True,
         "estimate": {"usd": None, "pricing_version": "p1"}},
    ]
    out = summarize_latest_calls(["101", "102", "103", "104"], mints, docs)
    assert out["101"]["call_status"] == "ended"
    assert out["101"]["estimated_usd"] == 0.0015
    assert out["101"]["estimate_status"] == "complete"
    assert out["101"]["usage_receipts"] == 2
    assert out["102"]["call_status"] == "failed"
    assert out["102"]["estimated_usd"] is None
    assert out["102"]["estimate_status"] == "unknown"
    assert out["103"]["environment"] == "development_test"
    assert out["103"]["estimate_status"] == "incomplete"
    assert out["103"]["estimated_usd"] is None
    assert out["103"]["known_estimated_usd"] == 0.002
    assert out["104"]["call_status"] == "no_call"
    assert out["104"]["estimated_usd"] is None


def test_newest_attempt_wins_for_room():
    mints = [mint("214", "old", "2026-10-21T01:00:00Z"), mint("214", "new", "2026-10-21T02:00:00Z")]
    docs = [{"kind": "session_ended", "session_id": "old", "reason": "resident_end_call"},
            {"kind": "session_ended", "session_id": "new", "reason": "setup_failed"}]
    assert summarize_latest_calls(["214"], mints, docs)["214"]["call_status"] == "failed"


def test_unknown_provenance_is_not_mislabeled_as_test_or_live():
    out = summarize_latest_calls(["9"], [mint("9", "s", "2026-10-21T01:00:00Z", purpose="", database="")], [])
    assert out["9"]["environment"] == "unknown"


def test_missing_usage_receipt_makes_partly_reported_call_incomplete():
    mints = [mint("214", "s1", "2026-10-21T01:00:00Z")]
    docs = [
        {"kind": "provider_usage", "session_id": "s1", "billable_activity": True, "counted": True,
         "estimate": {"usd": 0.001, "pricing_version": "p1"}},
        {"kind": "provider_usage", "session_id": "s1", "billable_activity": "unknown", "counted": True,
         "estimate": {"usd": None, "pricing_version": "p1"}},
    ]
    out = summarize_latest_calls(["214"], mints, docs)["214"]
    assert out["estimate_status"] == "incomplete"
    assert out["estimated_usd"] is None
    assert out["known_estimated_usd"] == 0.001
    assert out["usage_receipts"] == 2


def test_failed_mint_is_visible_even_without_session_end_receipt():
    out = summarize_latest_calls(
        ["214"], [mint("214", "s1", "2026-10-21T01:00:00Z", status=502)], []
    )["214"]
    assert out["call_status"] == "failed"
    assert out["estimate_status"] == "unknown"
    assert out["estimated_usd"] is None


def test_latest_by_room_rejects_unauthorized_request_before_reading_ledger():
    async def refused():
        raise HTTPException(status_code=403, detail="Admin access required")

    app = FastAPI()
    app.include_router(route.router)
    app.dependency_overrides[require_admin] = refused
    response = TestClient(app).get("/paid-api/call-costs/latest-by-room")
    assert response.status_code == 403
    assert response.json() == {"detail": "Admin access required"}
