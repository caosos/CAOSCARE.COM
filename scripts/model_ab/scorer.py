"""Scenario checks over a Session. Every check returns (ok, detail).

Check types (the only vocabulary scenarios.json may use) are in CHECKS.
Anything unknown is a hard schema error, never a silent pass.
"""
import re
from events import CLAIM_EVENTS


def _args_match(actual, want):
    for key, expected in want.items():
        if key not in (actual or {}):
            return False
        if isinstance(expected, dict) and "in" in expected:
            if actual[key] not in expected["in"]:
                return False
        elif actual[key] != expected:
            return False
    return True


def tool_called(s, c):
    for d in s.tool_calls(c["tool"]):
        if _args_match((d.get("meta") or {}).get("args"), c.get("args", {})):
            return True, ""
    return False, f"no {c['tool']} call matching {c.get('args', {})}"


def tool_result_ok(s, c):
    ok = any(((d.get("meta") or {}).get("result") or {}).get("ok") is True for d in s.tool_results(c["tool"]))
    return ok, "" if ok else f"no ok result for {c['tool']}"


def end_call_first_try_ok(s, c):
    results = s.tool_results("end_call")
    if not results:
        return False, "end_call never called"
    ok = ((results[0].get("meta") or {}).get("result") or {}).get("ok") is True
    return ok, "" if ok else "first end_call result was not ok"


def max_tool_calls(s, c):
    n = len(s.tool_calls(c["tool"]))
    return n <= c["n"], f"{n} calls to {c['tool']} (max {c['n']})"


def no_event(s, c):
    n = s.event_count(c["events"])
    return n == 0, f"{n} of {c['events']}"


def zero_unsupported_claims(s, c):
    n = s.event_count(CLAIM_EVENTS)
    return n == 0, f"{n} unsupported_* events"


def receipt_present(s, c):
    for r in s.receipts:
        if r.get("related_object_type") == c.get("related_object_type", r.get("related_object_type")) \
                and (not c.get("action_type") or r.get("action_type") == c["action_type"]):
            return True, ""
    return False, "no matching receipt"


def assistant_asks(s, c):
    rx = re.compile(c["pattern"], re.I)
    ok = any("?" in t and rx.search(t) for t in s.assistant_texts())
    return ok, "" if ok else "no clarifying question matching pattern"


def assistant_says(s, c):
    rx = re.compile(c["pattern"], re.I)
    ok = any(rx.search(t) for t in s.assistant_texts())
    return ok, "" if ok else "expected wording not found"


def assistant_never(s, c):
    rx = re.compile(c["pattern"], re.I)
    hits = [t for t in s.assistant_texts() if rx.search(t)]
    return not hits, f"forbidden wording: {hits[0][:60]!r}" if hits else ""


def claim_after_result(s, c):
    """A completion claim ('done') must come after an ok tool result."""
    rx = re.compile(c["pattern"], re.I)
    first_ok = next((d.get("created_at") for d in s.tool_results(c["tool"])
                     if ((d.get("meta") or {}).get("result") or {}).get("ok") is True), None)
    for d in s.of_type("assistant_transcript"):
        if rx.search(d.get("text") or ""):
            if first_ok is None or str(d.get("created_at")) < str(first_ok):
                return False, "completion claimed before an ok tool result"
            return True, ""
    return False, "no completion statement"


def one_of(s, c):
    for opt in c["options"]:
        if CHECKS[opt["type"]](s, opt)[0]:
            return True, ""
    return False, "none of the options held"


CHECKS = {f.__name__: f for f in (
    tool_called, tool_result_ok, end_call_first_try_ok, max_tool_calls, no_event,
    zero_unsupported_claims, receipt_present, assistant_asks, assistant_says,
    assistant_never, claim_after_result, one_of)}


def validate_scenarios(doc):
    """Raise ValueError on any schema problem (unknown check, empty turns, dup ids)."""
    ids = set()
    for sc in doc["scenarios"]:
        if not sc.get("id") or sc["id"] in ids:
            raise ValueError(f"missing or duplicate scenario id: {sc.get('id')}")
        ids.add(sc["id"])
        if not sc.get("turns") or not all(isinstance(t, str) and t for t in sc["turns"]):
            raise ValueError(f"{sc['id']}: turns must be non-empty strings")
        if not sc.get("checks"):
            raise ValueError(f"{sc['id']}: no checks")
        stack = list(sc["checks"])
        while stack:
            c = stack.pop()
            if c.get("type") not in CHECKS:
                raise ValueError(f"{sc['id']}: unknown check type {c.get('type')!r}")
            stack.extend(c.get("options", []))


def score_session(session, scenario):
    failed = []
    for c in scenario["checks"]:
        ok, detail = CHECKS[c["type"]](session, c)
        if not ok:
            failed.append(f"{c['type']}: {detail}")
    return {"session": session.session_id, "model": session.model, "scenario": scenario["id"],
            "passed": not failed, "failed": failed}
