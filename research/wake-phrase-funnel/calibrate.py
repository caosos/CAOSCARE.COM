"""Calibration from the completed 26-model Wake Word Lab (commit 772e216) - evidence only.

The lab measured, for 26 trained models, the catch rate at a matched simulated false-wake
rate. This fits a small linear model from text-stage features (the same features the funnel
computes for every new candidate) to that measured catch rate, and an empirical rate for
"reached the simulated ambient limit" by launcher / syllable count. Leave-one-out error is
reported so the predictor's weakness is visible. n = 26: this is a coarse prior, not a
measurement of any new candidate.

writes results/calibration.json
"""
import json
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
LAB = HERE.parents[1] / "firmware/voice-pe-aria/lab/results"
FEATURES = ["syllables", "phonemes_count", "launcher", "collision_margin"]


LAUNCHERS = {"hey", "hi", "hello", "okay"}


def has_launcher(text):
    w = text.split()
    return len(w) > 1 and w[0] in LAUNCHERS


def feats(r):
    m = r.get("collision_margin")
    return [r["syllables"], r["phonemes_count"], 1.0 if has_launcher(r["text"]) else 0.0,
            0.25 if m is None else min(m, 0.25)]       # None = nothing within 'near' -> cap


def main():
    p2 = json.loads((LAB / "phase2_results.json").read_text())["models"]
    rows = {r["id"]: r for r in json.loads((LAB / "discovery.json").read_text())["rows"]}
    for r in json.loads((LAB / "discovery_supplemental.json").read_text())["rows"]:
        rows.setdefault(r["id"], r)
    rec = json.loads((LAB / "recommendation.json").read_text())["ranked"]
    data = []
    for x in rec:
        r, m = rows[x["id"]], p2[x["slug"]]
        data.append({"id": x["id"], "x": feats(r), "tpr": m["matched_true_positive_rate_all_conditions"],
                     "reached": m["matched_ambient_false_per_hour"] <= 0.5, "launcher": has_launcher(r["text"]),
                     "syllables": r["syllables"]})
    X = np.array([[1.0] + d["x"] for d in data])
    y = np.array([d["tpr"] for d in data])
    coef, *_ = np.linalg.lstsq(X, y, rcond=None)
    pred = X @ coef
    r2 = 1 - ((y - pred) ** 2).sum() / ((y - y.mean()) ** 2).sum()
    loo = []
    for i in range(len(data)):
        k = np.arange(len(data)) != i
        c, *_ = np.linalg.lstsq(X[k], y[k], rcond=None)
        loo.append(abs(float(X[i] @ c) - y[i]))
    groups = {}
    for d in data:
        key = f"{'launcher' if d['launcher'] else 'bare'}_{min(d['syllables'], 6)}syl"
        g = groups.setdefault(key, [0, 0])
        g[0] += d["reached"]
        g[1] += 1
    reach = {"launcher": [sum(d["reached"] for d in data if d["launcher"]), sum(d["launcher"] for d in data)],
             "bare": [sum(d["reached"] for d in data if not d["launcher"]), sum(not d["launcher"] for d in data)]}
    out = {"source": "firmware/voice-pe-aria/lab results at commit 772e216 (26 trained models, synthetic evidence)",
           "target": "matched catch rate, all simulated conditions", "features": FEATURES,
           "coefficients": dict(zip(["intercept"] + FEATURES, [round(float(c), 5) for c in coef])),
           "r2_in_sample": round(float(r2), 3), "leave_one_out_mae": round(float(np.mean(loo)), 3),
           "reached_ambient_limit": {k: {"reached": v[0], "of": v[1]} for k, v in reach.items()},
           "reached_by_group": {k: {"reached": v[0], "of": v[1]} for k, v in sorted(groups.items())},
           "per_model": [{"id": d["id"], "measured_tpr": round(d["tpr"], 3), "fitted_tpr": round(float(p), 3),
                          "reached_ambient_limit": d["reached"]} for d, p in zip(data, pred)],
           "caution": "n=26, one synthetic voice set; use only to order candidates for testing, never as a "
                      "predicted real-room catch rate."}
    (HERE / "results/calibration.json").write_text(json.dumps(out, indent=1))
    print(json.dumps({k: out[k] for k in ("coefficients", "r2_in_sample", "leave_one_out_mae",
                                          "reached_ambient_limit")}, indent=1))


def predict(cal, syllables, phonemes_count, launcher, margin):
    c = cal["coefficients"]
    m = 0.25 if margin is None else min(margin, 0.25)
    return (c["intercept"] + c["syllables"] * syllables + c["phonemes_count"] * phonemes_count
            + c["launcher"] * (1.0 if launcher else 0.0) + c["collision_margin"] * m)


if __name__ == "__main__":
    main()
