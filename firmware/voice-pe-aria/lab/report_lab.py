"""Aggregate Phase 2 lab evaluations into side-by-side tables and raw CSV/JSON.

Two operating points per model:
  fixed   - the same cutoff for every model (lab_common.REPORT_CUTOFF)
  matched - for each model, the LOWEST cutoff (most sensitive setting) whose
            combined ambient false-activation rate is <= MATCHED_FAPH; this
            compares candidates at an equal false-wake budget (fairest comparison).
Outputs in lab/results/: phase2_results.json, phase2_summary.csv,
phase2_confusion.csv, phase2_cross_trigger.csv, phase2_roc.csv
"""
import csv
import json
import statistics
from collections import defaultdict

from lab_common import CUTOFFS, LAB, REPORT_CUTOFF, RUNS, load_trained_candidates

MATCHED_FAPH = 0.5
AMBIENT = ["tv_dialogue", "music", "background", "hvac", "silence"]
GROUPS = {
    "quiet_room_2m": ["room_2m"], "clean_near": ["clean"],
    "tv_on": ["tv_on_2m"], "other_talker": ["other_talker_2m"],
    "low_volume": ["soft_-18dB", "very_soft_-30dB"],
    "distance_1m": ["room_1m"], "distance_4m": ["room_4m"], "bed_facing_away": ["bed_facing_away_3m"],
    "hvac_music_noise": ["hvac_2m", "music_2m", "background_2m"],
    "weak_onset": ["weak_onset"], "short_final": ["short_final"], "run_together": ["run_together"],
    "older_sim": ["older_sim"], "raspy_sim": ["raspy_sim"], "dentures_sim": ["dentures_sim"],
}


def rate(vals, cut):
    return round(sum(v > cut for v in vals) / len(vals), 4) if vals else None


def ambient_faph(streams, cut):
    hours = sum(streams[s]["hours"] for s in AMBIENT)
    events = sum(streams[s]["events"][str(cut)] if str(cut) in streams[s]["events"] else streams[s]["events"][cut]
                 for s in AMBIENT)
    return round(events / hours, 3)


def main():
    cands = load_trained_candidates()
    res, conf, cross, roc = {}, defaultdict(dict), defaultdict(dict), []
    for c in cands:
        f = RUNS / c["slug"] / "lab_eval.json"
        if not f.exists():
            continue
        e = json.loads(f.read_text())
        st = {k: {**v, "events": {float(x): n for x, n in v["events"].items()}} for k, v in e["streams"].items()}
        own = defaultdict(list)
        forms = defaultdict(list)
        lat = []
        neg = defaultdict(list)
        pron = defaultdict(list)
        other = defaultdict(list)
        for r in e["clips"]:
            parts = r["file"].split("/")
            if parts[0] == "positives" and parts[1] == c["slug"]:
                own[r["condition"]].append(r["peak"])
                if r["condition"] == "clean":
                    forms[parts[2]].append(r["peak"])
                    if r["latency_ms"] is not None:
                        lat.append(r["latency_ms"])
            elif parts[0] == "positives":
                other[parts[1]].append(r["peak"])
            elif parts[0] == "pronunciation":
                pron[parts[2]].append(r["peak"])
            elif parts[0] in ("negatives_trained", "negatives_heldout", "sentences"):
                neg[(parts[0], parts[1])].append(r["peak"])
        matched = next((x for x in sorted(CUTOFFS) if ambient_faph(st, x) <= MATCHED_FAPH), max(CUTOFFS))
        row = {"id": c["id"], "slug": c["slug"], "kind": c["kind"], "launcher": c.get("launcher"),
               "base": c.get("base"), "tflite_sha256": e["tflite_sha256"], "tflite_bytes": e["tflite_bytes"],
               "arena_bytes": e["arena_bytes"], "matched_cutoff": matched}
        for point, cut in (("fixed", REPORT_CUTOFF), ("matched", matched)):
            allpos = [v for k in GROUPS for cond in GROUPS[k] for v in own[cond]]
            row[f"{point}_true_positive_rate_all_conditions"] = rate(allpos, cut)
            row[f"{point}_missed_wake_rate_all_conditions"] = round(1 - rate(allpos, cut), 4) if allpos else None
            for g, conds in GROUPS.items():
                row[f"{point}_tpr_{g}"] = rate([v for cnd in conds for v in own[cnd]], cut)
            for form, vals in forms.items():
                row[f"{point}_tpr_form_{form}"] = rate(vals, cut)
            for p, vals in pron.items():
                row[f"{point}_accept_{p}"] = rate(vals, cut)
            row[f"{point}_ambient_false_per_hour"] = ambient_faph(st, cut)
            for s in AMBIENT:
                row[f"{point}_false_per_hour_{s}"] = round(st[s]["events"][cut] / st[s]["hours"], 3)
            nvals = [v for vals in neg.values() for v in vals]
            row[f"{point}_confusion_false_activation_rate"] = rate(nvals, cut)
            row[f"{point}_sentence_false_activation_rate"] = rate(
                [v for (k, _), vals in neg.items() if k == "sentences" for v in vals], cut)
        row["detection_latency_ms_median"] = statistics.median(lat) if lat else None
        row["host_inference_ms_per_step"] = statistics.mean(st[s]["host_ms_per_inference"] for s in AMBIENT)
        res[c["slug"]] = row
        for (kind, phrase), vals in neg.items():
            conf[f"{kind}:{phrase}"][c["slug"]] = rate(vals, row["matched_cutoff"])
        for o, vals in other.items():
            cross[c["slug"]][o] = rate(vals, row["matched_cutoff"])
        for cut in CUTOFFS:
            roc.append({"slug": c["slug"], "cutoff": cut, "tpr_quiet_room_2m": rate(own["room_2m"], cut),
                        "tpr_tv_on": rate(own["tv_on_2m"], cut), "tpr_all": rate(
                            [v for k in GROUPS for cond in GROUPS[k] for v in own[cond]], cut),
                        "ambient_false_per_hour": ambient_faph(st, cut),
                        "confusion_false_rate": rate([v for vals in neg.values() for v in vals], cut)})
    out = LAB / "results"
    (out / "phase2_results.json").write_text(json.dumps({
        "report_cutoff": REPORT_CUTOFF, "matched_faph": MATCHED_FAPH, "ambient_streams": AMBIENT,
        "condition_groups": GROUPS, "models": res, "confusion_by_phrase_at_matched_cutoff": conf,
        "cross_trigger_at_matched_cutoff": cross, "roc": roc}, indent=1))
    keys = sorted({k for r in res.values() for k in r})
    head = ["id", "slug", "kind", "launcher", "base", "matched_cutoff"]
    keys = head + [k for k in keys if k not in head]
    with open(out / "phase2_summary.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        for r in res.values():
            w.writerow(r)
    slugs = list(res)
    with open(out / "phase2_confusion.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["phrase (false-activation rate at each model's matched cutoff)"] + slugs)
        for ph in sorted(conf):
            w.writerow([ph] + [conf[ph].get(s, "") for s in slugs])
    with open(out / "phase2_cross_trigger.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["model \\ spoken candidate"] + slugs)
        for s in slugs:
            w.writerow([s] + [cross[s].get(o, "" if o != s else "own") for o in slugs])
    with open(out / "phase2_roc.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(roc[0]))
        w.writeheader()
        w.writerows(roc)
    for r in sorted(res.values(), key=lambda r: -(r["matched_true_positive_rate_all_conditions"] or 0)):
        print(f"{r['id']:28s} cut={r['matched_cutoff']} TPR_all={r['matched_true_positive_rate_all_conditions']} "
              f"quiet={r['matched_tpr_quiet_room_2m']} tv={r['matched_tpr_tv_on']} "
              f"conf={r['matched_confusion_false_activation_rate']} FAPH={r['matched_ambient_false_per_hour']}")


if __name__ == "__main__":
    main()
