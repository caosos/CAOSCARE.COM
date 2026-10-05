"""Before/after report for the training-method A/B (okay_sequoia control vs okay_sequoia_tvneg).
Same aggregation as the lab (report_lab.main) into results/method_test/; pass target from
research/wake-phrase-funnel/method_test/PLAN_RECEIPT.md. usage: report_methodtest.py"""
import json

import report_lab
from lab_common import LAB, RUNS, load_all_candidates, load_batch_candidates, sha256

TARGET = {"ambient_faph_max": 0.5, "tpr_all_min": 0.63, "tpr_tv_on_min": 0.42, "confusion_max": 0.005}
PAIR = [("control", "okay_sequoia"), ("experiment", "okay_sequoia_tvneg")]


def main():
    out = LAB / "results/method_test"
    report_lab.main(load_all_candidates() + load_batch_candidates() + load_batch_candidates("methodtest"), out)
    p2 = json.loads((out / "phase2_results.json").read_text())["models"]
    rows = {}
    for role, s in PAIR:
        m = p2[s]
        cf = m["matched_confusion_rate_incl_extra"]
        r = {"slug": s, "threshold": m["matched_cutoff"], "catch_all": m["matched_true_positive_rate_all_conditions"],
             "catch_tv_on": m["matched_tpr_tv_on"], "catch_older_sim": m["matched_tpr_older_sim"],
             "catch_low_volume": m["matched_tpr_low_volume"], "wrong_word_rate": cf,
             "false_wakes_per_hour": m["matched_ambient_false_per_hour"],
             "false_wakes_per_hour_by_stream": {k: m[f"matched_false_per_hour_{k}"]
                                                for k in ("tv_dialogue", "music", "background", "hvac", "silence")},
             "catch_forms": {f: m.get(f"matched_tpr_form_{f}") for f in ("careful", "intended", "casual")},
             "fixed_0_90": {"catch_all": m["fixed_true_positive_rate_all_conditions"],
                            "false_wakes_per_hour": m["fixed_ambient_false_per_hour"]},
             "model_sha256": sha256(RUNS / s / "trained/tflite_stream_state_internal_quant/stream_state_internal_quant.tflite"),
             "lab_eval_sha256": sha256(RUNS / s / "lab_eval.json")}
        r["checks"] = {"false_wakes": r["false_wakes_per_hour"] <= TARGET["ambient_faph_max"],
                       "catch": (r["catch_all"] or 0) >= TARGET["tpr_all_min"],
                       "tv_catch": (r["catch_tv_on"] or 0) >= TARGET["tpr_tv_on_min"],
                       "wrong_word": cf <= TARGET["confusion_max"]}
        r["passes"] = all(r["checks"].values())
        rows[role] = r
    e1 = [(c["file"], c["condition"]) for c in json.loads((RUNS / "okay_sequoia/lab_eval.json").read_text())["clips"]]
    e2 = [(c["file"], c["condition"]) for c in json.loads((RUNS / "okay_sequoia_tvneg/lab_eval.json").read_text())["clips"]]
    s1 = json.loads((RUNS / "okay_sequoia/lab_eval.json").read_text())["streams"]
    s2 = json.loads((RUNS / "okay_sequoia_tvneg/lab_eval.json").read_text())["streams"]
    summary = {"target": TARGET, "control": rows["control"], "experiment": rows["experiment"],
               "result": "PASS" if rows["experiment"]["passes"] else "FAIL",
               "same_eval_jobs": sorted(e1) == sorted(e2), "eval_jobs": len(e2),
               "same_ambient_hours": {k: s1[k]["hours"] == s2[k]["hours"] for k in s1},
               "licensing": "RESEARCH ONLY - NOT COMMERCIALLY RELEASABLE"}
    (out / "method_test_summary.json").write_text(json.dumps(summary, indent=1))
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
