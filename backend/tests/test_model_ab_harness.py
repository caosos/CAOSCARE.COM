"""RQ-048 offline model A/B harness: scorer, scenario schema, budget guard,
dry-run plumbing against the local stub, static config report. No provider is
ever called; nothing here reads OPENAI_API_KEY from a file."""
import json
import os
import subprocess
import sys

import pytest

HARNESS = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "scripts", "model_ab"))
sys.path.insert(0, HARNESS)

import events as ev  # noqa: E402
import report  # noqa: E402
import run  # noqa: E402
import scorer  # noqa: E402


def _rows(sid, scenario, model, diag, receipts=()):
    rows = [{"collection": "run_meta", "doc": {"session_id": sid, "scenario_id": scenario, "model": model}}]
    for i, (etype, kw) in enumerate(diag):
        rows.append({"collection": "realtime_diagnostics", "doc": {
            "session_id": sid, "event_type": etype, "created_at": f"2026-01-01T00:00:{i:02d}+00:00", **kw}})
    rows += [{"collection": "receipts", "doc": r} for r in receipts]
    return rows


def test_scenarios_schema_valid_and_complete():
    sc = run.load_scenarios()
    assert [s["id"] for s in sc] == [f"S{i}" for i in range(1, 9)]


@pytest.mark.parametrize("bad", [
    {"scenarios": [{"id": "X", "turns": ["hi"], "checks": [{"type": "nope"}]}]},
    {"scenarios": [{"id": "X", "turns": [], "checks": [{"type": "no_event", "events": []}]}]},
    {"scenarios": [{"id": "X", "turns": ["a"], "checks": []}]},
    {"scenarios": [{"id": "X", "turns": ["a"], "checks": [{"type": "no_event", "events": []}]},
                   {"id": "X", "turns": ["a"], "checks": [{"type": "no_event", "events": []}]}]},
])
def test_schema_rejects_bad_scenarios(bad):
    with pytest.raises(ValueError):
        scorer.validate_scenarios(bad)


def test_scorer_pass_and_fail_on_known_events():
    sc = {"id": "T", "turns": ["x"], "checks": [
        {"type": "end_call_first_try_ok"}, {"type": "no_event", "events": ["unsupported_action_claim"]}]}
    ok = ev.Session(_rows("a", "T", "m", [
        ("tool_call", {"meta": {"name": "end_call", "args": {}}}),
        ("tool_result", {"meta": {"name": "end_call", "result": {"ok": True}}})]))
    assert scorer.score_session(ok, sc)["passed"]
    refused_then_ok = ev.Session(_rows("b", "T", "m", [
        ("tool_result", {"meta": {"name": "end_call", "result": {"ok": False}}}),
        ("tool_result", {"meta": {"name": "end_call", "result": {"ok": True}}})]))
    r = scorer.score_session(refused_then_ok, sc)
    assert not r["passed"] and "first end_call" in r["failed"][0]
    claim = ev.Session(_rows("c", "T", "m", [
        ("tool_result", {"meta": {"name": "end_call", "result": {"ok": True}}}),
        ("unsupported_action_claim", {"text": "I'll let the team know"})]))
    assert not scorer.score_session(claim, sc)["passed"]


def test_claim_after_result_and_receipt_checks():
    c = {"type": "claim_after_result", "tool": "toggle_light", "pattern": "done"}
    early = ev.Session(_rows("a", "T", "m", [
        ("assistant_transcript", {"text": "Done."}),
        ("tool_result", {"meta": {"name": "toggle_light", "result": {"ok": True}}})]))
    late = ev.Session(_rows("b", "T", "m", [
        ("tool_result", {"meta": {"name": "toggle_light", "result": {"ok": True}}}),
        ("assistant_transcript", {"text": "Done."})]))
    assert not scorer.CHECKS["claim_after_result"](early, c)[0]
    assert scorer.CHECKS["claim_after_result"](late, c)[0]
    rc = ev.Session(_rows("c", "T", "m", [], [{"related_object_type": "task", "action_type": "x"}]))
    assert scorer.CHECKS["receipt_present"](rc, {"related_object_type": "task"})[0]
    assert not scorer.CHECKS["receipt_present"](rc, {"related_object_type": "alert"})[0]


def test_cost_uses_only_recorded_prices_and_unknown_is_none():
    prices = report.load_prices()
    assert set(prices) == {"gpt-realtime", "gpt-realtime-2.1-mini"}
    totals = report.usage_totals([{"input_token_details": {"text_tokens": 1_000_000, "audio_tokens": 0},
                                   "output_token_details": {"text_tokens": 1_000_000}}])
    assert report.cost_usd(totals, prices["gpt-realtime"]) == 20.0       # 4 + 16
    assert report.cost_usd(totals, prices["gpt-realtime-2.1-mini"]) == 3.0  # 0.6 + 2.4
    assert report.cost_usd(totals, None) is None
    assert report.cost_usd(totals, {"text_in": 4, "text_out": None}) is None


def test_prices_file_has_no_invented_numbers():
    with open(os.path.join(HARNESS, "prices.json")) as fh:
        doc = json.load(fh)
    assert "re-verify" in doc["source"]
    nums = {m: {k: v for k, v in p.items()} for m, p in doc["models"].items()}
    assert nums["gpt-realtime"] == {"text_in": 4, "text_out": 16, "audio_in": 32, "audio_out": 64,
                                    "cached_text_in": 0.4, "cached_audio_in": 0.4}
    assert nums["gpt-realtime-2.1-mini"] == {"text_in": 0.6, "text_out": 2.4, "audio_in": 10, "audio_out": 20,
                                             "cached_text_in": 0.06, "cached_audio_in": 0.3}


@pytest.mark.parametrize("env,budget,needle", [
    ({}, None, "CAOSCARE_AB_APPROVED"),
    ({"OPENAI_API_KEY": "k"}, 2.0, "CAOSCARE_AB_APPROVED"),
    ({"CAOSCARE_AB_APPROVED": "da-x", "OPENAI_API_KEY": "k"}, None, "--budget-usd"),
    ({"CAOSCARE_AB_APPROVED": "da-x", "OPENAI_API_KEY": "k"}, 0, "--budget-usd"),
    ({"CAOSCARE_AB_APPROVED": "da-x", "OPENAI_API_KEY": "k"}, 50.0, "exceeds"),
    ({"CAOSCARE_AB_APPROVED": "da-x"}, 2.0, "OPENAI_API_KEY"),
])
def test_live_guard_refuses(env, budget, needle):
    with pytest.raises(SystemExit) as e:
        run.check_live_guard(env, budget)
    assert needle in str(e.value)


def test_live_mode_never_calls_a_provider(capsys, monkeypatch):
    called = []
    monkeypatch.setattr(run.urllib.request, "urlopen", lambda *a, **k: called.append(a))
    env = {"CAOSCARE_AB_APPROVED": "da-x", "OPENAI_API_KEY": "k"}
    rc = run.main(["--live", "--budget-usd", "2"], env=env)
    assert rc == 3 and not called
    assert "$2.00" in capsys.readouterr().out
    with pytest.raises(SystemExit):
        run.main(["--live"], env={})


def test_dry_run_plumbing_good_passes_bad_fails(tmp_path):
    results, sessions = run.run_dry(["stub-good", "stub-bad"], str(tmp_path))
    good = [r for r in results if r["model"] == "stub-good"]
    bad = [r for r in results if r["model"] == "stub-bad"]
    assert len(good) == len(bad) == 8
    assert all(r["passed"] for r in good), [r for r in good if not r["passed"]]
    assert not any(r["passed"] for r in bad)
    assert len(list(tmp_path.glob("*.jsonl"))) == 16            # one export per run
    summary = report.summarize(results, sessions, report.load_prices())
    assert summary["stub-bad"]["unsupported_claim_events"] > 0
    assert summary["stub-good"]["unsupported_claim_events"] == 0
    assert summary["stub-good"]["cost_usd"] is None             # no recorded price for a stub
    assert report.decide(summary["stub-good"], summary["stub-bad"])["adopt_candidate"] is False


def test_score_cli_reads_exports(tmp_path, capsys):
    run.run_dry(["stub-good"], str(tmp_path))
    import score
    files = [a for p in sorted(tmp_path.glob("*.jsonl")) for a in ("--jsonl", str(p))]
    assert score.main(files) == 0
    assert "PASS" in capsys.readouterr().out


def test_config_report_lists_fields_and_budget():
    out = subprocess.run([sys.executable, os.path.join(HARNESS, "config_check.py"), "--model", "gpt-realtime-2.1-mini"],
                         capture_output=True, text=True, timeout=120)
    assert out.returncode == 0, out.stderr[-500:]
    for needle in ("model = \"gpt-realtime-2.1-mini\"", "session.audio.input.noise_reduction.type",
                   "session.audio.input.turn_detection.create_response", "session.tools = [", "ESTIMATE"):
        assert needle in out.stdout
