"""Phase 3 - balanced recommendation from MEASURED Phase 2 results (all 22 models).

LICENSING IS A HARD GATE, NOT A SCORE (Michael, 2026-10-04): every current model was trained with
non-commercial data, so every model is RESEARCH ONLY - NOT COMMERCIALLY RELEASABLE, no candidate
earns points for licensing, and no binary is presented as shipping firmware.

Weighted score (0-10), weights fixed before results; every raw factor value is reported so the
weights can be changed later:
  true_wake          0.30  matched-point true-positive rate over all clip conditions          (acoustic)
  false_wake         0.30  10 x (1 - min(1, 5 x confusion false-activation rate, incl. the extra
                           Sivia-addendum confusion set scored on every model)) at the matched
                           point; 0 if the model cannot reach <= 0.5 ambient FA/h at any cutoff   (acoustic)
  older_resident     0.20  0.7 x measured TPR on resident conditions (older, raspy, dentures, weak
                           onset, shortened final, run-together, low volume) + 0.3 x Phase 1 text score
  memorability       0.10  HUMAN-FACTORS JUDGEMENT (Phase 1 rubric), not a measurement
  natural_identity   0.10  HUMAN-FACTORS JUDGEMENT: Aria family 10; human-like name 7; invented 4; noun 2

Naming / brand risk is a SEPARATE flag set (results/naming_risk.json, naming_risk.py) - common word,
personal name, resident/staff collision, product association, pronunciation and spelling ambiguity,
legal review required. It is never scored and never presented as licensing eligibility.

Finalists: top five by weighted score, at most one variant per base word.
Physical-test three: top three of the five, but at least one must be a memorable natural name
(memorability >= 8) if any such model meets minimum acoustics (matched TPR >= 0.6, confusion
false-activation rate <= 0.1, ambient <= 0.5 FA/h) - so the selection cannot collapse to
acoustically unusual but hard-to-remember invented words.
"""
import json

from lab_common import LAB, load_all_candidates, load_phase1_rows

W = {"true_wake": 0.30, "false_wake": 0.30, "older_resident": 0.20, "memorability": 0.10,
     "natural_identity": 0.10}
LICENSE_STATUS = "RESEARCH ONLY - NOT COMMERCIALLY RELEASABLE (training data includes non-commercial material)"
RESIDENT = ["older_sim", "raspy_sim", "dentures_sim", "weak_onset", "short_final", "run_together", "low_volume"]
NAMES = {"velora", "pomona", "callista", "kestra", "krysta", "zaria", "sivia"}


def base_word(c):
    t = c["text"].split()
    return t[-1] if t[0] in ("hey", "hi", "hello", "okay") and len(t) > 1 else c["text"]


def identity(c):
    b = base_word(c)
    if b == "aria":   # the assistant's own name (was a substring test, which also matched "zaria")
        return 10
    if b in NAMES:
        return 7
    if c["kind"] in ("invented",) or b in ("kolabamo", "kotrubo", "lumaro"):
        return 4
    return 2


def main():
    p2 = json.loads((LAB / "results/phase2_results.json").read_text())["models"]
    d1 = load_phase1_rows()
    risk = json.loads((LAB / "results/naming_risk.json").read_text())
    rows, not_evaluated = [], []
    cands = load_all_candidates()
    missing_screen = [c["id"] for c in cands if c["id"] not in d1]
    if missing_screen:
        raise SystemExit(f"no Phase 1 text-screen row for: {missing_screen}")
    for c in cands:
        m = p2.get(c["slug"])
        if not m:
            not_evaluated.append(c["id"])   # reported, never silently dropped or scored
            continue
        r1 = d1[c["id"]]
        tw = m["matched_true_positive_rate_all_conditions"] or 0
        reached = m["matched_ambient_false_per_hour"] <= 0.5
        cf = m.get("matched_confusion_rate_incl_extra")
        cf = m["matched_confusion_false_activation_rate"] if cf is None else cf
        cf = cf or 0
        fw = 10 * (1 - min(1.0, 5 * cf)) if reached else 0.0
        res = [m.get(f"matched_tpr_{g}") for g in RESIDENT if m.get(f"matched_tpr_{g}") is not None]
        older = 0.7 * 10 * (sum(res) / len(res) if res else 0) + \
            0.3 * r1["scores"]["measurable_text_stage"]["older_resident_pronunciation"]
        memo = r1["scores"]["subjective"]["memorability"]
        s = {"true_wake": round(10 * tw, 2), "false_wake": round(fw, 2), "older_resident": round(older, 2),
             "memorability": memo, "natural_identity": identity(c)}
        rows.append({"id": c["id"], "slug": c["slug"], "group": m["group"], "base": base_word(c),
                     "launcher": c["text"].split()[0] if c["text"].split()[0] in ("hey", "hi", "hello", "okay")
                     and len(c["text"].split()) > 1 else None,
                     "scores": s, "balanced": round(sum(W[k] * v for k, v in s.items()), 3),
                     "matched_tpr": tw, "confusion_rate": cf, "ambient_faph": m["matched_ambient_false_per_hour"],
                     "matched_cutoff": m["matched_cutoff"], "licensing_gate": LICENSE_STATUS,
                     "commercial_release_eligible": False, "human_factors_judgements": ["memorability",
                                                                                          "natural_identity"],
                     "naming_brand_risk": risk.get(c["slug"]),
                     "phase1_text_screen": "passed" if not r1["screen_rejected"] else "; ".join(r1["reject_reasons"])})
    # Deterministic order: score descending; an exact tie is broken by candidate id (alphabetical).
    rows.sort(key=lambda r: (-r["balanced"], r["id"]))
    # One finalist per base word: launcher forms and pronunciation variants of the same word compete
    # with each other, so variants of one word can never crowd a different word off the shortlist.
    five, seen, skipped_same_base = [], set(), []
    for r in rows:
        if len(five) == 5:
            break
        if r["base"] in seen:
            skipped_same_base.append({"id": r["id"], "balanced": r["balanced"], "base": r["base"]})
            continue
        five.append(r)
        seen.add(r["base"])
    three = five[:3]
    natural_ok = [r for r in rows if r["scores"]["memorability"] >= 8 and r["matched_tpr"] >= 0.6
                  and r["confusion_rate"] <= 0.1 and r["ambient_faph"] <= 0.5]
    rule_applied = None
    if natural_ok and not any(r["scores"]["memorability"] >= 8 for r in three):
        best_nat = next((r for r in natural_ok if r["base"] not in {x["base"] for x in three[:2]}), None)
        if best_nat:
            three = three[:2] + [best_nat]
            rule_applied = f"natural-name rule: '{best_nat['id']}' replaces #3 (meets minimum acoustics)"
    pairs = {}
    for r in rows:
        pairs.setdefault(r["base"], []).append(
            {"id": r["id"], "launcher": r["launcher"], "matched_tpr": r["matched_tpr"],
             "confusion_rate": r["confusion_rate"], "ambient_faph": r["ambient_faph"],
             "tpr_tv_on": p2[r["slug"]]["matched_tpr_tv_on"], "tpr_low_volume": p2[r["slug"]]["matched_tpr_low_volume"]})
    agreement = [{"id": r["id"], "phase1_text_screen": r["phase1_text_screen"], "matched_tpr": r["matched_tpr"],
                  "confusion_rate": r["confusion_rate"], "ambient_faph": r["ambient_faph"],
                  "balanced": r["balanced"]} for r in rows]
    out = {"weights": W, "licensing_gate": LICENSE_STATUS, "candidates_total": len(cands),
           "candidates_ranked": len(rows), "not_evaluated": not_evaluated, "ranked": rows, "five_finalists": [r["id"] for r in five],
           "physical_test_three": [r["id"] for r in three], "natural_name_rule": rule_applied,
           "selection_rules": ["rank by weighted score, ties broken by candidate id",
                               "five finalists = best-scoring candidate of each distinct base word",
                               "physical three = top three finalists, unless no memorability>=8 candidate is "
                               "in them and one meets TPR>=0.6, confusion<=0.1, ambient<=0.5/h (natural-name rule)"],
           "skipped_same_base_before_five_filled": skipped_same_base,
           "bare_vs_launcher": {b: v for b, v in pairs.items() if len(v) > 1},
           "text_screen_vs_acoustic": agreement,
           "note": "Synthetic evidence only. The final wake phrase is chosen from physical Voice PE tests."}
    (LAB / "results/recommendation.json").write_text(json.dumps(out, indent=1))
    for r in rows:
        print(f"{r['balanced']:5.2f} {r['id']:30s} {r['group'][:12]:12s} {r['scores']}")
    print(f"ranked {len(rows)}/{len(cands)}; not evaluated: {not_evaluated or 'none'}")
    print("five:", out["five_finalists"])
    print("three:", out["physical_test_three"], rule_applied or "")


if __name__ == "__main__":
    main()
