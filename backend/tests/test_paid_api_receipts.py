"""Backend receipts for paid Realtime requests (routes/paid_api_receipts.py): fake provider responses only."""
import asyncio
import uuid

import pytest
from fastapi import HTTPException

import paid_api_ledger as L
from routes import paid_api_receipts as R

run = asyncio.get_event_loop().run_until_complete
SECRET = "ek_test_secret_value_123"
USAGE = {"input_token_details": {"text_tokens": 900, "audio_tokens": 20, "cached_tokens": 800,
                                 "cached_tokens_details": {"text_tokens": 800, "audio_tokens": 0}},
         "output_token_details": {"text_tokens": 30, "audio_tokens": 60}}
BOUND_ENV = {"CAOSCARE_PAID_TEST_MAX_RESPONSES": "4", "CAOSCARE_PAID_TEST_MAX_TEXT_INPUT_TOKENS": "16000",
             "CAOSCARE_PAID_TEST_MAX_AUDIO_INPUT_TOKENS": "2000", "CAOSCARE_PAID_TEST_MAX_OUTPUT_TOKENS": "400",
             "CAOSCARE_PAID_TEST_MAX_SESSION_SECONDS": "300"}


class Resp:
    def __init__(self, status, body=None, headers=None):
        self.status_code, self._body, self.headers = status, body or {}, headers or {}

    def json(self):
        return self._body


MINTED = Resp(200, {"value": SECRET, "expires_at": 1792200000,
                    "session": {"id": "sess_abc", "model": "gpt-realtime-2.1-mini"}},
              {"x-request-id": "req_1", "openai-project": "proj_test"})


@pytest.fixture
def lg(monkeypatch):
    name = f"caoscare_ledger_test_{uuid.uuid4().hex[:8]}"
    ledger = L.PaidApiLedger(None, name)
    monkeypatch.setattr(R, "_ledger", ledger)
    for k in [*BOUND_ENV, "CAOSCARE_PAID_TEST_BUDGET_ID"]:
        monkeypatch.delenv(k, raising=False)
    yield ledger
    ledger.db.client.drop_database(name)


def mint(resp, **kw):
    run(R.record_mint(resp, requested_model="gpt-realtime-2.1-mini", purpose="resident_room_session",
                      session_id="rt_x1", started_at="2026-10-17T02:00:00+00:00", key="sk-test-key", room="214", **kw))


def test_mint_is_a_token_not_billable_activity_and_keeps_no_secret(lg):
    mint(MINTED)
    r = lg.db.receipts.find_one({"kind": "session_token_minted"}, {"_id": 0})
    assert r["billable_activity"] is False and r["usage"] is None and r["usage_status"] == "not_applicable"
    assert r["model_requested"] == r["model_provider"] == "gpt-realtime-2.1-mini"
    assert r["provider_session_id"] == "sess_abc" and r["provider_request_id"] == "req_1"
    assert r["provider_project"] == "proj_test" and r["key_id"] == L.key_id("sk-test-key")
    assert r["session_secret_fp"] == L.key_id(SECRET) and r["provenance"]["room"] == "214"
    assert SECRET not in repr(r) and "sk-test-key" not in repr(r)


def test_a_failed_mint_is_receipted_with_its_status(lg):
    mint(Resp(502))
    r = lg.db.receipts.find_one({"kind": "session_token_minted"})
    assert r["status"] == 502 and r["model_provider"] == "unknown" and r["session_secret_fp"] == "unknown"


def test_connect_is_the_billable_moment_and_links_to_its_mint(lg):
    mint(MINTED)
    run(R.record_connect(Resp(201, headers={"location": "/v1/realtime/calls/rtc_42"}),
                         ephemeral_key=SECRET, started_at="2026-10-17T02:00:01+00:00"))
    c = lg.db.receipts.find_one({"kind": "session_connected"})
    m = lg.db.receipts.find_one({"kind": "session_token_minted"})
    assert c["billable_activity"] is True and c["provider_call_id"] == "rtc_42"
    assert c["session_secret_fp"] == m["session_secret_fp"] and SECRET not in repr(c)


def test_usage_events_are_counted_once_and_missing_usage_stays_unknown(lg):
    meta = {"usage": USAGE, "status": "completed", "model": "gpt-realtime-2.1-mini",
            "provider_model": "gpt-realtime-2.1-mini", "provider_session_id": "sess_abc", "transport": "webrtc"}
    run(R.record_diagnostic("response_done", "rt_x1", "resp_9", meta, room="214"))
    run(R.record_diagnostic("response_done", "rt_x1", "resp_9", meta, room="214"))      # page retried the post
    run(R.record_diagnostic("response_done", "rt_x1", "resp_10", {"usage": None}, room="214"))
    run(R.record_diagnostic("speech_started", "rt_x1", None, {}, room="214"))           # not billing evidence
    counted = list(lg.db.receipts.find({"kind": "provider_usage", "counted": True}))
    assert [r["provider_response_id"] for r in counted] == ["resp_9", "resp_10"]
    assert counted[1]["usage_status"] == "unknown" and counted[1]["estimate"]["usd"] is None
    assert lg.db.receipts.count_documents({"kind": "provider_usage", "counted": False}) == 1
    assert lg.db.receipts.count_documents({}) == 3


def test_a_partly_reported_usage_is_incomplete_not_zero(lg):
    run(R.record_diagnostic("response_done", "rt_x1", "resp_p", {"usage": {"input_token_details": {"text_tokens": 5}}}))
    r = lg.db.receipts.find_one({"provider_response_id": "resp_p"})
    assert r["usage_status"] == "incomplete" and r["estimate"]["usd"] is None


def test_live_rooms_are_never_gated(lg):
    assert run(R.reserve_for_test("gpt-realtime-2.1-mini", "resident_room_session", "rt_live")) is None


def test_paid_test_without_a_budget_or_bounds_is_refused_before_minting(lg, monkeypatch):
    monkeypatch.setenv("CAOSCARE_PAID_TEST_BUDGET_ID", "probe_budget")
    with pytest.raises(HTTPException) as no_budget:
        run(R.reserve_for_test("gpt-realtime-2.1-mini", "probe", "rt_t1"))
    assert no_budget.value.status_code == 503 and "cap is unknown" in no_budget.value.detail
    lg.budget.open_budget("probe_budget", 1.0, "owner (unit test)")
    with pytest.raises(HTTPException) as no_bounds:
        run(R.reserve_for_test("gpt-realtime-2.1-mini", "probe", "rt_t1"))
    assert "bound is missing" in no_bounds.value.detail


def test_paid_test_session_reserves_settles_and_closes(lg, monkeypatch):
    monkeypatch.setenv("CAOSCARE_PAID_TEST_BUDGET_ID", "probe_budget")
    for k, v in BOUND_ENV.items():
        monkeypatch.setenv(k, v)
    lg.budget.open_budget("probe_budget", 1.0, "owner (unit test)")
    rid = run(R.reserve_for_test("gpt-realtime-2.1-mini", "probe", "rt_t2"))
    run(R.record_mint(MINTED, requested_model="gpt-realtime-2.1-mini", purpose="probe", session_id="rt_t2",
                      started_at="2026-10-17T02:00:00+00:00", key="sk-test-key", reservation_id=rid))
    run(R.record_diagnostic("response_done", "rt_t2", "resp_t", {"usage": USAGE}))
    run(R.record_diagnostic("session_ended", "rt_t2", None, {"reason": "resident_end_call"}))
    b = lg.budget.state("probe_budget")
    assert b["open_count"] == 0 and b["reserved_usd"] == pytest.approx(0) and b["spent_usd"] > 0
    assert lg.db.reservations.find_one({"reservation_id": rid})["status"] == "closed"


def test_a_failed_mint_releases_its_reservation(lg, monkeypatch):
    monkeypatch.setenv("CAOSCARE_PAID_TEST_BUDGET_ID", "probe_budget")
    for k, v in BOUND_ENV.items():
        monkeypatch.setenv(k, v)
    lg.budget.open_budget("probe_budget", 1.0, "owner (unit test)")
    rid = run(R.reserve_for_test("gpt-realtime-2.1-mini", "probe", "rt_t3"))
    mint(Resp(500), reservation_id=rid)
    assert lg.db.reservations.find_one({"reservation_id": rid})["closed_reason"] == "mint_failed"
    assert lg.budget.state("probe_budget")["reserved_usd"] == pytest.approx(0)


def test_a_broken_ledger_never_breaks_a_live_call(monkeypatch):
    class Broken:
        def record(self, *a, **k):
            raise RuntimeError("ledger down")
    monkeypatch.setattr(R, "_ledger", Broken())
    mint(MINTED)   # no exception


def test_a_self_test_event_is_never_an_openai_charge(lg):
    run(R.record_diagnostic("response_done", "selftest_1", "selftest_resp_1",
                            {"usage": USAGE, "provider": "caoscare-selftest", "model": "gpt-realtime-2.1-mini"}))
    r = lg.db.receipts.find_one({"provider_response_id": "selftest_resp_1"})
    assert r["provider"] == "caoscare-selftest" and r["dedupe_key"] == "caoscare-selftest:response:selftest_resp_1"
    assert lg.db.receipts.count_documents({"kind": "provider_usage", "provider": "openai"}) == 0
