"""Model A/B runner.

--dry-run (default, the only executable mode): drives each scenario's typed
turns against the local STUB endpoint over HTTP, writes an export JSONL per
run, scores it, prints the table, summary and decision. Proves plumbing only.

--live: GUARDED and not implemented in RQ-048. It refuses unless the owner
approval statement id (env CAOSCARE_AB_APPROVED), a --budget-usd cap (<= 5.0,
the proposal's cap) and OPENAI_API_KEY (env only, never read from files) are
present; it prints the cap and then stops. No provider is ever called here.
"""
import argparse
import json
import os
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import events as ev  # noqa: E402
import report  # noqa: E402
import scorer  # noqa: E402
from stub_realtime import start_stub  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
MAX_BUDGET_USD = 5.0  # proposal section 6 cap


def load_scenarios():
    with open(os.path.join(HERE, "scenarios.json"), encoding="utf-8") as fh:
        doc = json.load(fh)
    scorer.validate_scenarios(doc)
    return doc["scenarios"]


def check_live_guard(env, budget):
    """Return the spend cap if live may start, else raise SystemExit(2)."""
    problems = []
    if not (env.get("CAOSCARE_AB_APPROVED") or "").strip():
        problems.append("env CAOSCARE_AB_APPROVED=<owner statement id> is required")
    if budget is None or budget <= 0:
        problems.append("--budget-usd <cap> is required and must be > 0")
    elif budget > MAX_BUDGET_USD:
        problems.append(f"--budget-usd {budget} exceeds the approved cap of ${MAX_BUDGET_USD}")
    if not env.get("OPENAI_API_KEY"):
        problems.append("OPENAI_API_KEY must be in the environment (never read from files)")
    if problems:
        raise SystemExit("REFUSING live run (proposal section 7 gate):\n  - " + "\n  - ".join(problems))
    return budget


def post_turn(base_url, payload):
    req = urllib.request.Request(base_url + "/v1/realtime/typed-turn", data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read())["events"]


def run_dry(models, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    scenarios = load_scenarios()
    srv, base = start_stub()
    results, sessions = [], []
    try:
        for model in models:
            for sc in scenarios:
                sid = f"dry-{model}-{sc['id']}"
                rows = [{"collection": "run_meta", "doc": {"session_id": sid, "scenario_id": sc["id"], "model": model}}]
                for i, text in enumerate(sc["turns"]):
                    rows += post_turn(base, {"model": model, "scenario_id": sc["id"], "turn_index": i,
                                             "text": text, "session_id": sid})
                path = os.path.join(out_dir, f"{sid}.jsonl")
                ev.dump_jsonl(rows, path)
                s = ev.Session(ev.load_jsonl(path))
                sessions.append(s)
                results.append(scorer.score_session(s, sc))
    finally:
        srv.shutdown()
    return results, sessions


def main(argv=None, env=None):
    env = os.environ if env is None else env
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="stub endpoint only (default)")
    mode.add_argument("--live", action="store_true", help="guarded; never runs in RQ-048")
    ap.add_argument("--budget-usd", type=float)
    ap.add_argument("--models", default="stub-good,stub-bad")
    ap.add_argument("--out", default=os.path.join(HERE, "out"))
    a = ap.parse_args(argv)
    if a.live:
        cap = check_live_guard(env, a.budget_usd)
        print(f"Spend cap: ${cap:.2f} total. Live driver is NOT implemented in RQ-048; nothing was called.")
        return 3
    results, sessions = run_dry([m.strip() for m in a.models.split(",")], a.out)
    print(report.format_table(results))
    summary = report.summarize(results, sessions, report.load_prices())
    print(json.dumps(summary, indent=2))
    models = list(summary)
    if len(models) >= 2:
        print(json.dumps(report.decide(summary[models[0]], summary[models[1]]), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
