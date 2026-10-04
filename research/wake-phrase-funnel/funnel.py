"""Run the qualification funnel and write every output. Deterministic, no audio, no training.

Stage 1 - mechanical gates (any failure rejects; reasons recorded):
  benchmark rows are excluded; written word contains an embarrassing substring; Wake Phrase Lab
  hard gates (G4 failures caused only by rare names < 0.01% are advisory, same policy as the
  26-model lab); own first name >= 0.1% of people (likely resident/staff name); estimated
  duration > 1.35 s (microWakeWord 1.5 s window); fewer than 3 syllables; same sound as an
  earlier candidate.
  Survivors are ordered by mechanical score; the best 250 form the qualified list.
Stage 2 - human suitability (preliminary rules): dignity >= 7, memorability >= 6, senior
  speakability >= 6, brand suitability >= 3, pronunciation ambiguity <= 4. Survivors ordered by
  total preliminary score; the best 100 form Michael's review list.
Nothing advances to model training without Michael's approval.

usage: python funnel.py      (Wake Phrase Lab venv)
"""
import csv
import json
import sys
from collections import Counter
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "tools" / "wakelab"))
from wakelab.config import settings    # noqa: E402
from wakelab.rank import census_share   # noqa: E402

from score import MAX_SECONDS, MIN_SYLLABLES, WEIGHTS, bases, score_one  # noqa: E402

R = HERE / "results"
QUALIFIED_N, REVIEW_N = 250, 100
COMMON_NAME_PERCENT = 0.1
HUMAN_MIN = {"dignity_naturalness": 7, "memorability": 6, "senior_speakability": 6, "brand_suitability": 3}
HUMAN_MAX_AMBIGUITY = 4
COLUMNS = ["rank", "stage_reached", "status", "written_phrase", "intended_pronunciation", "approx_phonemes",
           "syllables", "stress", "category", "form", "base", "identity_flag", "pronunciation_ambiguity",
           "pronunciation_ambiguity_note", "senior_speakability", "memorability", "dignity_naturalness",
           "dignity_notes", "brand_suitability", "common_speech_collision_risk", "similar_name_collision_risk",
           "similar_names", "tv_background_speech_risk", "predicted_acoustic_distinctiveness",
           "predicted_catch_rate_prior", "nearest_collisions", "trademark_review_flag", "gates_failed",
           "mechanical_score", "total_preliminary_score", "pass_fail", "rejection_reason"]


def mechanical_reasons(c, r, seen_sound):
    why = []
    if c["category"] == "benchmark":
        why.append("acoustic benchmark only - not a product candidate")
    if r["_embarrassing"]:
        why.append("dignity: " + r["dignity_notes"])
    hard = [g for g in r["gates_failed"] if g != "G4_domain_names_commands" or r["_g4_hard"]]
    if hard:
        why.append("text collision gates failed: " + ", ".join(hard))
    if (r["_own_name_percent"] or 0) >= COMMON_NAME_PERCENT:
        why.append(f"common first name ({r['_own_name_percent']}% of people): likely resident/staff name")
    if r["_seconds"] > MAX_SECONDS:
        why.append(f"too long for the 1.5 s detection window (est. {r['_seconds']} s)")
    if r["syllables"] < MIN_SYLLABLES:
        why.append(f"too short ({r['syllables']} syllables; minimum {MIN_SYLLABLES})")
    key = tuple(bases(c["phonemes"]))
    if key in seen_sound and c["category"] != "benchmark":
        why.append(f"same sound as '{seen_sound[key]}'")
    seen_sound.setdefault(key, c["id"])
    return why


def human_reasons(r):
    why = [f"{k.replace('_', ' ')} {r[k]} < {v}" for k, v in HUMAN_MIN.items() if r[k] < v]
    if r["pronunciation_ambiguity"] > HUMAN_MAX_AMBIGUITY:
        why.append(f"pronunciation ambiguity {r['pronunciation_ambiguity']} > {HUMAN_MAX_AMBIGUITY}")
    return why


def write_csv(path, rows):
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({k: ("; ".join(v) if isinstance(v, list) else v) for k, v in r.items()})


def main():
    lists = yaml.safe_load(open(HERE / "lists.yaml"))
    cands = json.loads((R / "candidates_generated.json").read_text())["candidates"]
    screen = {json.loads(x)["id"]: json.loads(x) for x in (R / "screen_raw.jsonl").read_text().splitlines() if x}
    missing = [c["id"] for c in cands if c["id"] not in screen]
    if missing:
        raise SystemExit(f"{len(missing)} candidates not screened yet (e.g. {missing[:3]})")
    cal = json.loads((R / "calibration.json").read_text())
    share, near = census_share(), settings()["distance"]["near"]
    rows, seen_sound = [], {}
    for c in cands:                              # generation order: deterministic dedupe winner
        r = score_one(c, screen[c["id"]], lists, share, near, cal)
        r["mechanical_rejection"] = mechanical_reasons(c, r, seen_sound)
        r["human_rejection"] = human_reasons(r)
        rows.append(r)
    passers = sorted([r for r in rows if not r["mechanical_rejection"]],
                     key=lambda r: (-r["mechanical_score"], r["written_phrase"]))
    qualified = passers[:QUALIFIED_N]
    qset = {r["written_phrase"] for r in qualified}
    human_ok = sorted([r for r in qualified if not r["human_rejection"]],
                      key=lambda r: (-r["total_preliminary_score"], r["written_phrase"]))
    review = human_ok[:REVIEW_N]
    rset = {r["written_phrase"] for r in review}
    for r in rows:
        if r["mechanical_rejection"]:
            r["stage_reached"], r["status"], r["pass_fail"] = "generated", "REJECTED (mechanical)", "fail"
            r["rejection_reason"] = "; ".join(r["mechanical_rejection"])
        elif r["written_phrase"] not in qset:
            r["stage_reached"], r["status"], r["pass_fail"] = "mechanical pass", "below top-250 cut", "fail"
            r["rejection_reason"] = f"mechanical score {r['mechanical_score']} below the {QUALIFIED_N}th survivor"
        elif r["human_rejection"]:
            r["stage_reached"], r["status"], r["pass_fail"] = "qualified (top 250)", "REJECTED (human suitability)", "fail"
            r["rejection_reason"] = "; ".join(r["human_rejection"])
        elif r["written_phrase"] not in rset:
            r["stage_reached"], r["status"], r["pass_fail"] = "human-suitable", "below top-100 cut", "fail"
            r["rejection_reason"] = f"total score {r['total_preliminary_score']} below the {REVIEW_N}th"
        else:
            r["stage_reached"], r["status"], r["pass_fail"] = "review list (top 100)", "FOR MICHAEL'S REVIEW", "pass"
            r["rejection_reason"] = ""
        if r["category"] == "benchmark":
            r["status"] = "BENCHMARK - acoustic reference only"
    for i, r in enumerate(sorted(rows, key=lambda r: (-r["total_preliminary_score"], r["written_phrase"])), 1):
        r["rank"] = i
    for r in rows:
        for k in [k for k in r if k.startswith("_")]:
            del r[k]
    rows.sort(key=lambda r: r["rank"])
    product = [r for r in rows if r["category"] != "benchmark"]
    stage = lambda pred: [r for r in product if pred(r)]  # noqa: E731
    mech = stage(lambda r: not r["mechanical_rejection"])
    summary = {
        "generated": len(product), "benchmarks_excluded": len(rows) - len(product),
        "mechanical_survivors": len(mech), "qualified_top250": len(qualified),
        "human_suitable_within_qualified": len(human_ok), "review_list_top100": len(review),
        "weights": WEIGHTS, "human_minimums": HUMAN_MIN, "human_max_ambiguity": HUMAN_MAX_AMBIGUITY,
        "category_distribution": {
            "generated": dict(Counter(r["category"] for r in product)),
            "mechanical_survivors": dict(Counter(r["category"] for r in mech)),
            "qualified_top250": dict(Counter(r["category"] for r in qualified)),
            "human_suitable": dict(Counter(r["category"] for r in human_ok)),
            "review_top100": dict(Counter(r["category"] for r in review))},
        "form_distribution_review": dict(Counter(r["form"] for r in review)),
        "new_identity_in_review": sum(r["identity_flag"].startswith("NEW") for r in review),
        "top_mechanical_rejection_reasons": Counter(
            x.split(":")[0].split("(")[0].strip() for r in product for x in r["mechanical_rejection"]).most_common(),
        "aria_family": [{k: r[k] for k in ("written_phrase", "status", "rejection_reason", "total_preliminary_score")}
                        for r in rows if r["category"] == "aria"],
        "licensing": "No model trained. Any future model for these phrases inherits the lab's licensing gate.",
    }
    (R / "funnel_all.json").write_text(json.dumps(rows, indent=1))
    write_csv(R / "funnel_all.csv", rows)
    write_csv(R / "rejected.csv", [r for r in rows if r["pass_fail"] == "fail"])
    (R / "top250_qualified.json").write_text(json.dumps(qualified, indent=1))
    write_csv(R / "top250_qualified.csv", qualified)
    (R / "top100_review.json").write_text(json.dumps(review, indent=1))
    write_csv(R / "top100_review.csv", review)
    (R / "funnel_summary.json").write_text(json.dumps(summary, indent=1))
    print(json.dumps({k: summary[k] for k in ("generated", "mechanical_survivors", "qualified_top250",
                                              "human_suitable_within_qualified", "review_list_top100")}))
    print(json.dumps(summary["category_distribution"], indent=0))


if __name__ == "__main__":
    main()
