"""Session event model for the A/B harness: load an export, query it.

An export is JSONL; each line is {"collection": <name>, "doc": {...}}.
Collections used: realtime_diagnostics, conversations, receipts, run_meta
(run_meta carries session_id / scenario_id / model for harness-made runs).
Stdlib only. Mongo reading is optional (pymongo imported lazily).
"""
import json
from datetime import datetime

CLAIM_EVENTS = ("unsupported_action_claim", "unsupported_fresh_fact_claim", "unsupported_lookup_claim")


def parse_ts(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def load_jsonl(path):
    rows = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def dump_jsonl(rows, path):
    with open(path, "w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, sort_keys=True, default=str) + "\n")


def read_mongo(mongo_url, db_name, session_id):
    """Read one session's rows from a (throwaway) Mongo DB. Never writes."""
    from pymongo import MongoClient  # lazy: not needed for JSONL scoring
    db = MongoClient(mongo_url, serverSelectionTimeoutMS=3000)[db_name]
    rows = []
    for coll, key in (("realtime_diagnostics", "session_id"), ("conversations", "session_id"),
                      ("receipts", "conversation_session_id")):
        for doc in db[coll].find({key: session_id}, {"_id": 0}).sort("created_at", 1):
            rows.append({"collection": coll, "doc": doc})
    return rows


class Session:
    """One session's rows with the queries the scorer needs."""

    def __init__(self, rows, session_id=None, scenario_id=None, model=None):
        meta = next((r["doc"] for r in rows if r.get("collection") == "run_meta"), {})
        self.session_id = session_id or meta.get("session_id")
        self.scenario_id = scenario_id or meta.get("scenario_id")
        self.model = model or meta.get("model") or "unknown"
        self.diag = [r["doc"] for r in rows if r.get("collection") == "realtime_diagnostics"]
        self.receipts = [r["doc"] for r in rows if r.get("collection") == "receipts"]
        self.diag.sort(key=lambda d: str(d.get("created_at", "")))  # ISO strings sort chronologically

    def of_type(self, event_type):
        return [d for d in self.diag if d.get("event_type") == event_type]

    def tool_calls(self, name=None):
        return [d for d in self.of_type("tool_call") if name is None or (d.get("meta") or {}).get("name") == name]

    def tool_results(self, name=None):
        return [d for d in self.of_type("tool_result") if name is None or (d.get("meta") or {}).get("name") == name]

    def assistant_texts(self):
        return [d.get("text") or "" for d in self.of_type("assistant_transcript")]

    def event_count(self, types):
        return sum(1 for d in self.diag if d.get("event_type") in types)

    def latencies_ms(self):
        """Typed resident turn -> next response_created, from logged timestamps."""
        out, pending = [], None
        for d in self.diag:
            t = parse_ts(d.get("created_at"))
            if d.get("event_type") == "user_transcript":
                pending = t
            elif d.get("event_type") == "response_created" and pending and t:
                out.append((t - pending).total_seconds() * 1000.0)
                pending = None
        return out

    def usages(self):
        return [(d.get("meta") or {}).get("usage") for d in self.of_type("response_done")
                if (d.get("meta") or {}).get("usage")]
