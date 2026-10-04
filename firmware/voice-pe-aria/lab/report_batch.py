"""Report an acoustic batch beside the 26-model benchmarks without rewriting the lab's results.

1. Runs report_lab's identical aggregation over the 26 lab models + the batch, written to
   lab/results/<batch>/ (the 26-model results in lab/results/ are untouched).
2. Scores every model with recommend_lab's weights. Batch phrases have no Phase 1 lab row, so the
   text-stage inputs come from the wake-phrase funnel (senior speakability -> older-resident text
   component, memorability as recorded). Natural identity uses recommend_lab's scale (real name 7,
   invented 4); reported addition: a role phrase (no new name, Aria kept) scores 7.
3. Applies the pre-registered decision rule (research/wake-phrase-funnel/batch1/SELECTION_RECEIPT.md)
   and writes lab/results/<batch>/batch_summary.json.

usage: report_batch.py [batch1]     (research venv)
"""
import json
import sys

import report_lab
from lab_common import LAB, load_all_candidates, load_batch_candidates
from recommend_lab import RESIDENT, W

RULE = {"ambient_faph_max": 0.5, "tpr_all_min": 0.63, "tpr_tv_on_min": 0.42, "confusion_max": 0.005}
# recommend_lab's natural-identity scale (Aria 10, a real name 7, invented 4) mapped onto funnel
# categories: real word/first name 7, invented 4; role phrase 7 (reported addition - Aria is kept).
IDENTITY = {"word_name": 7, "given_name": 7, "constructed": 4, "role": 7}
BENCHMARKS = ["hey_kookaburra", "hey_callista_kuh_liss_tuh", "okay_velora_veh_lor_uh", "hey_aria"]


def score(m, older_text, memo, ident):
    tw = m["matched_true_positive_rate_all_conditions"] or 0
    reached = m["matched_ambient_false_per_hour"] <= 0.5
    cf = m.get("matched_confusion_rate_incl_extra")
    cf = (m["matched_confusion_false_activation_rate"] if cf is None else cf) or 0
    res = [m[f"matched_tpr_{g}"] for g in RESIDENT if m.get(f"matched_tpr_{g}") is not None]
    s = {"true_wake": round(10 * tw, 2), "false_wake": round(10 * (1 - min(1.0, 5 * cf)) if reached else 0.0, 2),
         "older_resident": round(0.7 * 10 * (sum(res) / len(res) if res else 0) + 0.3 * older_text, 2),
         "memorability": memo, "natural_identity": ident}
    return s, round(sum(W[k] * v for k, v in s.items()), 3), cf


def main(name="batch1"):
    batch = load_batch_candidates(name)
    out = LAB / "results" / name
    report_lab.main(load_all_candidates() + batch, out)
    p2 = json.loads((out / "phase2_results.json").read_text())["models"]
    lab_rec = {r["slug"]: r for r in json.loads((LAB / "results/recommendation.json").read_text())["ranked"]}
    rows = []
    for c in batch:
        m = p2.get(c["slug"])
        if not m:
            rows.append({"id": c["id"], "slug": c["slug"], "status": "NOT EVALUATED (see lab_logs/failures)"})
            continue
        ident = IDENTITY[c["kind"]]
        s, total, cf = score(m, c["funnel_senior_speakability"], c["funnel_memorability"], ident)
        checks = {"ambient_ok": m["matched_ambient_false_per_hour"] <= RULE["ambient_faph_max"],
                  "tpr_all_ok": (m["matched_true_positive_rate_all_conditions"] or 0) >= RULE["tpr_all_min"],
                  "tv_on_ok": (m["matched_tpr_tv_on"] or 0) >= RULE["tpr_tv_on_min"],
                  "confusion_ok": cf <= RULE["confusion_max"]}
        rows.append({"id": c["id"], "slug": c["slug"], "kind": c["kind"], "identity_flag": c["identity_flag"],
                     "status": "evaluated", "scores": s, "weighted": total, "matched_cutoff": m["matched_cutoff"],
                     "tpr_all": m["matched_true_positive_rate_all_conditions"], "tpr_tv_on": m["matched_tpr_tv_on"],
                     "tpr_low_volume": m["matched_tpr_low_volume"],
                     "tpr_older_sim": m["matched_tpr_older_sim"], "tpr_raspy_sim": m["matched_tpr_raspy_sim"],
                     "tpr_dentures_sim": m["matched_tpr_dentures_sim"],
                     "tpr_forms": {f: m.get(f"matched_tpr_form_{f}") for f in ("careful", "intended", "casual")},
                     "confusion_rate": cf, "ambient_faph": m["matched_ambient_false_per_hour"],
                     "checks": checks, "clearly_outperforms": all(checks.values())})
    bench = []
    for s in BENCHMARKS:
        m, r = p2[s], lab_rec[s]
        bench.append({"id": r["id"], "slug": s, "weighted_lab": r["balanced"], "matched_cutoff": m["matched_cutoff"],
                      "tpr_all": m["matched_true_positive_rate_all_conditions"], "tpr_tv_on": m["matched_tpr_tv_on"],
                      "tpr_low_volume": m["matched_tpr_low_volume"], "confusion_rate": r["confusion_rate"],
                      "ambient_faph": m["matched_ambient_false_per_hour"]})
    cross = json.loads((out / "phase2_results.json").read_text())["cross_trigger_at_matched_cutoff"]
    worst_cross = {r["slug"]: max(((o, v) for o, v in cross.get(r["slug"], {}).items() if v), key=lambda x: x[1],
                                  default=None) for r in rows}
    passed = [r["id"] for r in rows if r.get("clearly_outperforms")]
    decision = ("STOP - report for physical-test consideration" if len(passed) >= 2
                else "Recommend a second batch of at most 8 (not started automatically)")
    summary = {"batch": name, "rule": RULE, "decision": decision, "passed": passed,
               "rows": sorted(rows, key=lambda r: -(r.get("weighted") or -1)), "benchmarks": bench,
               "worst_cross_trigger_per_batch_model": worst_cross,
               "scoring_note": "recommend_lab weights; text inputs from the funnel for batch phrases; role phrase "
                               "natural identity = 7 (reported addition)",
               "licensing": "RESEARCH ONLY - NOT COMMERCIALLY RELEASABLE"}
    (out / "batch_summary.json").write_text(json.dumps(summary, indent=1))
    for r in summary["rows"]:
        print(r.get("weighted"), r["id"], r.get("tpr_all"), r.get("tpr_tv_on"), r.get("confusion_rate"),
              r.get("ambient_faph"), r.get("checks"))
    print("decision:", decision, passed)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "batch1")
