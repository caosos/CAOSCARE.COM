"""Paid API ledger + paid-test budget guard: offline, local MongoDB only, synthetic ids, no provider calls.
Owner cost directive 2026-10-16/17: attribution, survival across resets, retries, cancellations, duplicates,
missing usage and concurrent reservations."""
import os
import re
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pymongo
import pytest

import paid_api_ledger as L

URL = os.environ.get("MONGO_URL") or "mongodb://localhost:27017"
USAGE = {"total_tokens": 15250, "input_tokens": 15100, "output_tokens": 150,
         "input_token_details": {"text_tokens": 15000, "audio_tokens": 100, "cached_tokens": 14000,
                                 "cached_tokens_details": {"text_tokens": 14000, "audio_tokens": 0}},
         "output_token_details": {"text_tokens": 50, "audio_tokens": 100}}
BOUNDS = dict(model="gpt-realtime-2.1-mini", max_responses=4, max_text_input_tokens=16000,
              max_audio_input_tokens=2000, max_output_tokens=400, max_session_seconds=300)


@pytest.fixture
def ledger():
    name = f"caoscare_ledger_test_{uuid.uuid4().hex[:8]}"
    yield L.PaidApiLedger(URL, name)
    pymongo.MongoClient(URL).drop_database(name)


def usage_event(lg, rid, usage=USAGE, session="rt_test_1", status="completed"):
    return lg.record_usage(provider="openai", provider_response_id=rid, usage=usage,
                           model_requested="gpt-realtime-2.1-mini", model_provider="gpt-realtime-2.1-mini",
                           status=status, session_id=session, provider_session_id="sess_test",
                           provenance=L.provenance("probe", test="unit"))


def test_receipt_carries_attribution_and_no_secrets_or_content(ledger, monkeypatch):
    monkeypatch.setenv("CAOSCARE_RUN_ID", "run_probe_7")
    monkeypatch.setenv("CAOSCARE_RUN_PURPOSE", "scratch-acceptance")
    out = usage_event(ledger, "resp_1")
    r = ledger.db.receipts.find_one({"receipt_id": out["receipt_id"]}, {"_id": 0})
    assert out["counted"] and r["kind"] == "provider_usage" and r["pricing_version"] == L.PRICING_VERSION
    assert r["provenance"]["run_id"] == "run_probe_7" and r["provenance"]["run_purpose"] == "scratch-acceptance"
    assert r["provenance"]["pid"] == os.getpid() and r["provider_session_id"] == "sess_test"
    assert r["model_requested"] == r["model_provider"] == "gpt-realtime-2.1-mini" and r["status"] == "completed"
    assert r["usage"] == USAGE and r["usage_status"] == "reported"          # provider fields kept as reported
    # 1000 uncached text, 14000 cached text, 100 audio in, 50 text out, 100 audio out at mini prices
    assert r["estimate"] == {"usd": round((1000 * .6 + 14000 * .06 + 100 * 10 + 50 * 2.4 + 100 * 20) / 1e6, 8),
                             "pricing_version": L.PRICING_VERSION, "basis": "provider_usage"}
    assert "provider_billed_usd" not in r                                      # billing is never inferred
    flat = repr(r).lower()
    assert not any(w in flat for w in ("transcript", "instructions", "audio_b64", "sk-", "bearer"))
    assert L.key_id("sk-live-abc123") .startswith("keyfp_") and "abc" not in L.key_id("sk-live-abc123")


def test_missing_usage_is_unknown_never_zero(ledger):
    out = usage_event(ledger, "resp_2", usage=None)
    r = ledger.db.receipts.find_one({"receipt_id": out["receipt_id"]})
    assert r["usage"] is None and r["usage_status"] == "unknown"
    assert r["estimate"]["usd"] is None and r["billable_activity"] == "unknown"


def test_duplicate_usage_is_kept_but_counted_once(ledger):
    first = usage_event(ledger, "resp_dup")
    again = usage_event(ledger, "resp_dup")
    assert first["counted"] and not again["counted"] and again["duplicate_of"] == first["receipt_id"]
    assert ledger.db.receipts.count_documents({"dedupe_key": "openai:response:resp_dup"}) == 2
    assert ledger.db.receipts.count_documents({"dedupe_key": "openai:response:resp_dup", "counted": True}) == 1


def test_usage_without_a_provider_id_is_kept_and_never_counted(ledger):
    out = usage_event(ledger, None)
    assert not out["counted"]
    assert ledger.db.receipts.find_one({"receipt_id": out["receipt_id"]})["provider_response_id"] == "unknown"


def test_receipts_survive_a_scratch_seed_reset_and_test_cleanup(ledger):
    scratch = pymongo.MongoClient(URL)[f"caoscare_scratch_{uuid.uuid4().hex[:8]}"]
    scratch.realtime_diagnostics.insert_one({"event_type": "response_done", "response_id": "resp_s"})
    usage_event(ledger, "resp_s")
    scratch.realtime_diagnostics.delete_many({})                 # what the scratch seed --reset did
    scratch.client.drop_database(scratch.name)                   # what a test gate's cleanup does
    assert ledger.db.name != scratch.name and ledger.db.receipts.count_documents({"provider_response_id": "resp_s"}) == 1


def test_ledger_database_never_follows_db_name(monkeypatch):
    monkeypatch.setenv("DB_NAME", "caoscare_gate_x")
    monkeypatch.delenv("CAOSCARE_LEDGER_DB", raising=False)
    lg = L.PaidApiLedger(URL)
    assert lg.db.name == "caoscare_paid_api_ledger"


def test_ledger_code_never_updates_or_deletes_a_receipt():
    src = Path(L.__file__).read_text() + Path(L.__file__).with_name("paid_api_budget.py").read_text()
    assert not re.search(r"receipts\.(update|delete|replace|find_one_and_|drop|remove)", src)


# -- budget guard ------------------------------------------------------------------------------------------

def test_no_budget_means_no_paid_test(ledger):
    out = ledger.budget.reserve("nope", provenance={}, **BOUNDS)
    assert out == {"ok": False, "reason": "no owner-approved budget exists (the cap is unknown)"}
    assert ledger.db.receipts.count_documents({"kind": "budget_refused"}) == 1


def test_unknown_price_or_missing_bound_is_refused(ledger):
    ledger.budget.open_budget("b", 5.0, "owner")
    assert not ledger.budget.reserve("b", provenance={}, **{**BOUNDS, "model": "gpt-new-unpriced"})["ok"]
    assert not ledger.budget.reserve("b", provenance={}, **{**BOUNDS, "max_session_seconds": None})["ok"]
    assert not ledger.budget.reserve("b", provenance={}, **{**BOUNDS, "max_output_tokens": 0})["ok"]


def test_a_budget_needs_an_owner_cap():
    lg = L.PaidApiLedger(URL, f"caoscare_ledger_test_{uuid.uuid4().hex[:8]}")
    try:
        for cap, who in ((0, "owner"), (None, "owner"), (5, "")):
            with pytest.raises(ValueError):
                lg.budget.open_budget("b", cap, who)
    finally:
        lg.db.client.drop_database(lg.db.name)


def test_concurrent_reservations_never_pass_the_cap(ledger):
    worst = L.worst_case_usd(BOUNDS["model"], 4, 16000, 2000, 400)
    ledger.budget.open_budget("b", worst * 5 + worst / 2, "owner")       # room for exactly five
    with ThreadPoolExecutor(20) as pool:
        outs = list(pool.map(lambda _: ledger.budget.reserve("b", provenance={}, **BOUNDS), range(20)))
    assert sum(o["ok"] for o in outs) == 5
    b = ledger.budget.state("b")
    assert b["reserved_usd"] + b["spent_usd"] <= b["cap_usd"] and b["open_count"] == 5


def test_usage_settles_and_close_releases_the_rest(ledger):
    ledger.budget.open_budget("b", 5.0, "owner")
    res = ledger.budget.reserve("b", provenance={}, **BOUNDS)
    ledger.budget.bind_session(res["reservation_id"], "rt_s1")
    est = usage_event(ledger, "resp_a", session="rt_s1")
    usage_event(ledger, "resp_a", session="rt_s1")                       # duplicate: settled once
    spent = ledger.db.receipts.find_one({"receipt_id": est["receipt_id"]})["estimate"]["usd"]
    assert ledger.budget.state("b")["spent_usd"] == pytest.approx(spent)
    assert ledger.budget.close(res["reservation_id"], "session_ended")
    b = ledger.budget.state("b")
    assert b["reserved_usd"] == pytest.approx(0) and b["open_count"] == 0 and b["unknown_count"] == 0


def test_cancelled_response_with_partial_usage_is_counted(ledger):
    ledger.budget.open_budget("b", 5.0, "owner")
    res = ledger.budget.reserve("b", provenance={}, **BOUNDS)
    ledger.budget.bind_session(res["reservation_id"], "rt_c")
    out = usage_event(ledger, "resp_cut", session="rt_c", status="cancelled",
                      usage={**USAGE, "output_token_details": {"text_tokens": 5, "audio_tokens": 12}})
    r = ledger.db.receipts.find_one({"receipt_id": out["receipt_id"]})
    assert out["counted"] and r["status"] == "cancelled" and r["estimate"]["usd"] > 0
    assert ledger.budget.state("b")["spent_usd"] == pytest.approx(r["estimate"]["usd"])


def test_missing_usage_blocks_new_paid_tests_until_reconciled(ledger):
    ledger.budget.open_budget("b", 5.0, "owner")
    res = ledger.budget.reserve("b", provenance={}, **BOUNDS)
    ledger.budget.bind_session(res["reservation_id"], "rt_u")
    usage_event(ledger, "resp_u", usage=None, session="rt_u")
    ledger.budget.close(res["reservation_id"], "session_ended")
    b = ledger.budget.state("b")
    assert b["unknown_count"] == 1 and b["reserved_usd"] == pytest.approx(res["reserved_usd"])   # stays counted
    refused = ledger.budget.reserve("b", provenance={}, **BOUNDS)
    assert not refused["ok"] and "unknown" in refused["reason"]
    assert ledger.budget.reconcile_unknown(res["reservation_id"], 0.0123, "provider export 2026-10-17")
    assert ledger.budget.reserve("b", provenance={}, **BOUNDS)["ok"]
    billed = ledger.db.receipts.find_one({"kind": "provider_billing"})
    assert billed["provider_billed_usd"] == 0.0123 and billed["source"] == "provider export 2026-10-17"


def test_retry_is_its_own_reservation_linked_to_the_first(ledger):
    ledger.budget.open_budget("b", 5.0, "owner")
    first = ledger.budget.reserve("b", provenance={}, **BOUNDS)
    ledger.budget.close(first["reservation_id"], "connect_failed")
    retry = ledger.budget.reserve("b", provenance={}, retry_of=first["reservation_id"], **BOUNDS)
    assert retry["ok"] and retry["reservation_id"] != first["reservation_id"]
    r = ledger.db.receipts.find_one({"kind": "budget_reserved", "reservation_id": retry["reservation_id"]})
    assert r["retry_of"] == first["reservation_id"]


def test_a_session_open_past_its_deadline_becomes_unknown_and_blocks(ledger, monkeypatch):
    ledger.budget.open_budget("b", 5.0, "owner")
    res = ledger.budget.reserve("b", provenance={}, **BOUNDS)
    later = L.now() + L.timedelta(seconds=BOUNDS["max_session_seconds"] + L.STALE_GRACE_S + 5)
    monkeypatch.setattr(L, "now", lambda: later)
    refused = ledger.budget.reserve("b", provenance={}, **BOUNDS)
    assert not refused["ok"] and "unknown" in refused["reason"]
    assert ledger.db.reservations.find_one({"reservation_id": res["reservation_id"]})["status"] == "stale"
    assert ledger.db.receipts.count_documents({"kind": "budget_stale"}) == 1


def test_running_past_a_bound_is_receipted(ledger):
    ledger.budget.open_budget("b", 5.0, "owner")
    res = ledger.budget.reserve("b", provenance={}, **{**BOUNDS, "max_responses": 1})
    ledger.budget.bind_session(res["reservation_id"], "rt_b")
    usage_event(ledger, "resp_b1", session="rt_b")
    usage_event(ledger, "resp_b2", session="rt_b")
    assert ledger.db.receipts.count_documents({"kind": "budget_bound_exceeded"}) >= 1


def test_model_names_match_prices_only_through_a_date_suffix():
    # gpt-4o-mini-tts / -transcribe were once priced as gpt-4o-mini text (a prefix match); never again.
    import paid_api_pricing as P
    assert P._model_key("gpt-4o-mini-2024-07-18", P.TEXT) == "gpt-4o-mini"
    assert P._model_key("gpt-4o-mini-tts", P.TEXT) is None and P._model_key("gpt-4o-mini-transcribe", P.TEXT) is None
    assert P.estimate_usd("gpt-4o-mini-tts", {"input_tokens": 55, "output_tokens": 255}) == round((55 * 0.60 + 255 * 12.00) / 1e6, 8)
    assert P.estimate_usd("gpt-4o-mini-transcribe", {"input_tokens": 25, "output_tokens": 10}) == round((25 * 1.25 + 10 * 5.00) / 1e6, 8)
