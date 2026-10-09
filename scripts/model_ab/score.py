"""Score recorded sessions (never calls a provider).

  score.py --jsonl run.jsonl [--jsonl ...]            export files (run_meta rows label them)
  score.py --mongo-url URL --db DB --session SID:SCENARIO:MODEL [...]   read-only
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import events as ev  # noqa: E402
import report  # noqa: E402
import scorer  # noqa: E402
from run import load_scenarios  # noqa: E402


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--jsonl", action="append", default=[])
    ap.add_argument("--mongo-url")
    ap.add_argument("--db")
    ap.add_argument("--session", action="append", default=[], help="SID:SCENARIO:MODEL")
    ap.add_argument("--prices")
    a = ap.parse_args(argv)
    by_id = {s["id"]: s for s in load_scenarios()}
    sessions = [ev.Session(ev.load_jsonl(p)) for p in a.jsonl]
    for spec in a.session:
        sid, scn, model = spec.split(":", 2)
        sessions.append(ev.Session(ev.read_mongo(a.mongo_url, a.db, sid), sid, scn, model))
    results = [scorer.score_session(s, by_id[s.scenario_id]) for s in sessions]
    print(report.format_table(results))
    print(json.dumps(report.summarize(results, sessions, report.load_prices(a.prices)), indent=2))
    return 0 if all(r["passed"] for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
