"""Human-readable rendering of an inspect result (the JSON is the full record)."""
import json
import os
import re

from .config import RUNS_DIR

METRIC_LABELS = [("exact", "exact phonetic collisions"), ("near", "near collisions"),
                 ("phrase", "inside longer words/phrases"), ("boundary", "across word boundaries"),
                 ("contains", "common words hidden inside"), ("domain", "facility/domain"),
                 ("names", "names"), ("distress", "distress/safety words"),
                 ("clipped", "clipped start/end"), ("variants", "accent/casual variants")]


def _neighbour(f):
    freq = (f"zipf {f['zipf']}" if f["metric"] == "common_word" and f["zipf"] is not None
            else f"{f['per_million']:.2f}/million" if f.get("per_million") and f["metric"] == "phrase"
            else f["source"] if f["metric"] != "domain" else f"{f['category']} (authored)")
    how = "IDENTICAL phonemes" if f["distance"] == 0 else f"distance {f['distance']:.2f}"
    extra = ""
    if f.get("variant_rule"):
        extra = f"  via {f['variant_desc']} -> {f['variant_phonemes']}"
    if f.get("clip"):
        extra = f"  when {f['clip']} -> {f['clipped_phonemes']}"
    itself = "  (the candidate word itself, in ordinary use)" if f.get("is_candidate_itself") else ""
    return f"\"{f['text']}\"  [{f['phonemes']}]  {f['metric']}, {freq}, {f['relation']}, {how}{extra}{itself}"


def _unique(items):
    seen, out = set(), []
    for f in items:
        if f["text"] not in seen:
            seen.add(f["text"])
            out.append(f)
    return out


def _dangerous_phrases(e):
    exact_words = {f["text"] for f in e["metrics"]["exact"] + e["metrics"]["near"] if f["metric"] == "common_word"}
    pool = e["metrics"]["phrase"] + e["metrics"]["domain"] + e["metrics"]["boundary"]
    hits = [f for f in pool if " " in f["text"] and (f["relation"] == "boundary"
                                                     or any(w in f["text"].split() for w in exact_words))]
    hits.sort(key=lambda f: (f["distance"], -(f.get("per_million") or 0)))
    return _unique(hits)[:10]


def render(r):
    L = [f"WAKE PHRASE LAB - inspect \"{r['candidate']}\"",
         "(text/phoneme stage: predicts acoustic danger, does not prove it)", "",
         f"VERDICT: {r['verdict']}", ""]
    for e in r["pronunciations"]:
        tag = {"intended": "INTENDED pronunciation (authoritative)",
               "dictionary": "dictionary pronunciation (judged)",
               "informational": "other dictionary pronunciation (information only - cannot rescue the candidate)"}[e["role"]]
        L += [f"== {e['phonemes']}   {tag}", f"   source: {e['source']}",
              f"   result: {e['verdict']}" + (f"  - failed {', '.join(e['failed_gates'])}" if e["failed_gates"] else "")]
        for g in e["gates"]:
            if g["result"] != "FAIL":
                continue
            L += [f"   x {g['gate']}: {g['title']}", f"     why: {g['why']}"]
            L += [f"       - {_neighbour(f)}" for f in _unique(g["evidence"])[:5]]
        phrases = _dangerous_phrases(e)
        if phrases:
            L.append("   dangerous everyday phrases carrying this sound:")
            L += [f"       - {_neighbour(f)}" for f in phrases[:6]]
        passed = [g["gate"] for g in e["gates"] if g["result"] == "PASS"]
        if passed:
            L.append("   passed: " + ", ".join(passed))
        L.append("   separate metrics (counts): " + " | ".join(
            f"{label} {e['metric_counts'][k]}" for k, label in METRIC_LABELS))
        risk = e["risk_per_hour"]
        L.append("   rough exposure, look-alike events per hour of speech: " +
                 (", ".join(f"{k} {v}" for k, v in risk.items()) if risk else "none measured"))
        s = e["speakability"]
        L.append(f"   speakability (separate; never offsets a collision): {s['syllables']} syllables, "
                 f"stress {s['stress_pattern'] or '-'}, onset {s['onset']}, "
                 f"{s['distinct_consonants']} consonants/{s['distinct_vowels']} vowels distinct, "
                 f"max cluster {s['max_consonant_cluster']}" + ("; " + "; ".join(s["notes"]) if s["notes"] else ""))
        L.append("")
    L += ["LIMITATION: " + r["limitation"],
          f"timing: corpus load {r['timing_seconds']['corpus_load']}s, inspect {r['timing_seconds']['inspect']}s"]
    return "\n".join(L)


def save(r, text, out_dir=None):
    slug = re.sub(r"[^a-z0-9]+", "-", r["candidate"].lower()).strip("-") or "candidate"
    stamp = r["generated_at"][:19].replace(":", "").replace("-", "")
    path = out_dir or os.path.join(RUNS_DIR, f"{stamp}_{slug}")
    os.makedirs(path, exist_ok=True)
    with open(os.path.join(path, "report.json"), "w", encoding="utf-8") as fh:
        json.dump(r, fh, indent=2, sort_keys=True, default=str)
    with open(os.path.join(path, "report.md"), "w", encoding="utf-8") as fh:
        fh.write("```\n" + text + "\n```\n")
    return path
