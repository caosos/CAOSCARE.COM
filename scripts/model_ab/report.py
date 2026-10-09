"""Per-model summary, usage/cost from response.done usage, decision gates."""
import json
import os
from events import CLAIM_EVENTS

HERE = os.path.dirname(os.path.abspath(__file__))


def load_prices(path=None):
    with open(path or os.path.join(HERE, "prices.json"), encoding="utf-8") as fh:
        return json.load(fh)["models"]


def percentile(values, p):
    if not values:
        return None
    v = sorted(values)
    return v[min(len(v) - 1, int(round(p * (len(v) - 1))))]


def usage_totals(usages):
    """Sum response.done usage. Shape (provider Realtime response.done):
    input_token_details{text_tokens,audio_tokens,cached_tokens,
    cached_tokens_details{text_tokens,audio_tokens}}, output_token_details{...}.
    Verify against a real response before relying on it (not run here)."""
    t = dict(text_in=0, audio_in=0, cached_text_in=0, cached_audio_in=0, text_out=0, audio_out=0)
    for u in usages:
        i, o = u.get("input_token_details") or {}, u.get("output_token_details") or {}
        cd = i.get("cached_tokens_details") or {}
        ct, ca = cd.get("text_tokens", i.get("cached_tokens", 0) or 0), cd.get("audio_tokens", 0)
        t["cached_text_in"] += ct
        t["cached_audio_in"] += ca
        t["text_in"] += max(0, (i.get("text_tokens") or 0) - ct)
        t["audio_in"] += max(0, (i.get("audio_tokens") or 0) - ca)
        t["text_out"] += o.get("text_tokens") or 0
        t["audio_out"] += o.get("audio_tokens") or 0
    return t


def cost_usd(totals, price):
    """None (unknown) if any needed price is missing or null - never guessed."""
    if not price:
        return None
    total = 0.0
    for key, tokens in totals.items():
        if not tokens:
            continue
        if price.get(key) is None:
            return None
        total += tokens * price[key] / 1_000_000
    return round(total, 6)


def summarize(results, sessions, prices):
    """results: score_session dicts; sessions: Session objects (same order)."""
    by_model = {}
    for r, s in zip(results, sessions):
        m = by_model.setdefault(r["model"], dict(runs=0, passed=0, claims=0, errors=0, lat=[], usages=[], failed=[]))
        m["runs"] += 1
        m["passed"] += r["passed"]
        m["claims"] += s.event_count(CLAIM_EVENTS)
        m["errors"] += s.event_count(("realtime_error",))
        m["lat"] += s.latencies_ms()
        m["usages"] += s.usages()
        if not r["passed"]:
            m["failed"].append(r["scenario"])
    out = {}
    for model, m in by_model.items():
        totals = usage_totals(m["usages"]) if m["usages"] else None
        out[model] = dict(
            runs=m["runs"], passed=m["passed"], failed_scenarios=m["failed"],
            unsupported_claim_events=m["claims"], realtime_errors=m["errors"],
            latency_p50_ms=percentile(m["lat"], 0.5), latency_p95_ms=percentile(m["lat"], 0.95),
            usage=totals if totals else "not logged",
            cost_usd=cost_usd(totals, prices.get(model)) if totals else None)
    return out


def decide(base, cand):
    """Proposal section 5 gates. Any failure or unknown -> keep the baseline."""
    gates = {
        "tool correctness (all scenarios pass)": cand["passed"] >= base["passed"] and not cand["failed_scenarios"],
        "zero unsupported claims": cand["unsupported_claim_events"] == 0,
        "no session errors": cand["realtime_errors"] == 0,
        "p95 latency not worse": (cand["latency_p95_ms"] is not None and base["latency_p95_ms"] is not None
                                  and cand["latency_p95_ms"] <= base["latency_p95_ms"]),
    }
    return {"gates": gates, "adopt_candidate": all(gates.values()),
            "note": "Any failed or unknown gate keeps the baseline (Baseline 5a; proposal section 5)."}


def format_table(results):
    lines = [f"{'session':<22} {'model':<24} {'scn':<4} result"]
    for r in results:
        res = "PASS" if r["passed"] else "FAIL: " + "; ".join(r["failed"])
        lines.append(f"{str(r['session']):<22} {r['model']:<24} {r['scenario']:<4} {res}")
    return "\n".join(lines)
