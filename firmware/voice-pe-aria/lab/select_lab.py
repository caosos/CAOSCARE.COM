"""Phase 1 -> Phase 2: choose the 10-15 candidates to train, with recorded reasons.

Rules (METHODOLOGY.md), ranking only by the MEASURABLE text-stage composite:
 A. comparison baselines (Michael): aria, hey aria, zaria - trained even if the
    text screen rejected them.
 B. first-request Aria variants (okay aria, aria care, hey zaria) that pass.
 C. per family (invented / invented with ST-SK-KR-TR-KT / real word): best
    passing base + its best passing launcher, so a prefix is MEASURED.
 D. nominated names (Michael) and human names: best passing launcher phrase
    of the family + its bare name (trained even if the bare name failed text).
 F. fill to MAX_TRAINED with the next best passing base.
 Everything not advanced gets a recorded reason.
Also writes lab_neighbours.json: each trained candidate's two nearest corpus
neighbours become shared TRAINING negatives; the next two become HELD-OUT
evaluation negatives.
"""
import json
import re

from lab_common import LAB, SAMPLES

MAX_TRAINED = 15
BASELINES = ["aria", "hey aria", "zaria"]
REQUESTED_ARIA_VARIANTS = ["okay aria", "aria care", "hey zaria"]
CLUSTERS = {"ST", "SK", "KR", "TR", "KT"}


def slug(s):
    return re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")


def arpa_words(row):
    """Split phonemes into words where the first word is a known launcher (hey/hi/hello/okay)."""
    ph = row["phonemes"].split()
    first = row["text"].split()[0]
    n = {"hey": 2, "hi": 2, "hello": 4, "okay": 3}.get(first)
    if n and len(row["text"].split()) > 1:
        return [" ".join(ph[:n]), " ".join(ph[n:])]
    return [" ".join(ph)]


def main():
    rows = json.loads((LAB / "results/discovery.json").read_text())["rows"]
    by_id = {r["id"]: r for r in rows}
    chosen, why = [], {}

    def take(r, reason):
        chosen.append(r)
        why[r["id"]] = reason

    for b in BASELINES:
        take(by_id[b], "rule A - comparison baseline (Michael); text screen: "
             + ("passed" if not by_id[b]["screen_rejected"] else "; ".join(by_id[b]["reject_reasons"])))
    passed = [r for r in rows if not r["screen_rejected"] and r["kind"] != "control"]
    for v in REQUESTED_ARIA_VARIANTS:     # rule B - first-request variants that pass the text screen
        r = by_id[v]
        if not r["screen_rejected"]:
            take(r, f"rule B - requested Aria variant, passed text screen (rank {r['rank']})")
    bases = [r for r in passed if r["kind"] != "launcher"]

    def launchers_of(base_id, only_passed=True):
        pool = passed if only_passed else rows
        btext = by_id[base_id]["text"]
        return sorted((x for x in pool if x.get("base") == base_id or (
            x["kind"] == "phrase" and x["text"].split()[0] in ("hey", "hi", "hello", "okay")
            and x["text"].split(maxsplit=1)[-1] == btext)), key=lambda x: -x["measurable_composite"])

    def has_cluster(r):
        ph = [p.rstrip("012") for p in r["phonemes"].split()]
        return any(a + b in CLUSTERS for a, b in zip(ph, ph[1:]))

    families = [("invented, no consonant cluster", lambda r: r["kind"] == "invented" and not has_cluster(r)),
                ("invented, internal ST/SK/KR/TR/KT", lambda r: r["kind"] == "invented" and has_cluster(r)),
                ("real word", lambda r: r["kind"] == "word")]
    for fam, ok in families:          # rule C - best base per family + its best passing launcher
        cand = [b for b in sorted(bases, key=lambda b: -b["measurable_composite"]) if ok(b)
                and launchers_of(b["id"]) and b["id"] not in why]
        if cand:
            b, l = cand[0], launchers_of(cand[0]["id"])[0]
            take(b, f"rule C - best passing {fam} base (rank {b['rank']}, measurable {b['measurable_composite']})")
            take(l, f"rule C - best passing launcher of '{b['id']}' (rank {l['rank']}): prefix measured, not assumed")
    for fam, kind in (("nominated name (Michael)", "nominated"), ("human name", "name")):
        ls = sorted((x for x in passed if x["kind"] == "launcher" and by_id[x["base"]]["kind"] == kind),
                    key=lambda x: -x["measurable_composite"])
        if ls:                        # rule D/E - best passing launcher of the family + its bare name
            l, b = ls[0], by_id[ls[0]["base"]]
            take(l, f"rule D - best passing {fam} phrase (rank {l['rank']}, measurable {l['measurable_composite']})")
            take(b, f"rule D - bare '{b['id']}' trained to measure the launcher effect; text screen: "
                 + ("passed" if not b["screen_rejected"] else "; ".join(b["reject_reasons"])))
    for b in sorted(bases, key=lambda b: -b["measurable_composite"]):   # rule F - fill
        if len(chosen) >= MAX_TRAINED:
            break
        if b["id"] not in why and b["kind"] != "aria":
            take(b, f"rule F - next best passing base (rank {b['rank']}, measurable {b['measurable_composite']})")
    chosen = chosen[:MAX_TRAINED]

    trained = [{"id": r["id"], "text": r["text"], "slug": slug(r["id"]), "kind": r["kind"],
                "base": r.get("base"), "launcher": r.get("launcher"), "phonemes": r["phonemes"],
                "arpa_words": arpa_words(r), "phase1_rank": r["rank"],
                "phase1_measurable": r["measurable_composite"], "phase1_subjective": r["subjective_composite"],
                "advance_reason": why[r["id"]]} for r in chosen]
    for t in trained:   # pronunciation-sensitivity diagnostics for the Aria family
        if "aria" in t["text"]:
            alt = [w.replace("AA1 R IY0 AH0", "EH1 R IY0 AH0") for w in t["arpa_words"]]
            t["alt_pronunciations"] = [{"label": "AIR-ee-uh (area-like)", "arpa_words": alt}]
    (LAB / "trained_candidates.json").write_text(json.dumps(trained, indent=1))
    decisions = []
    for r in rows:
        if r["id"] in why:
            decisions.append({"id": r["id"], "decision": "advanced to Phase 2", "reason": why[r["id"]]})
        elif r["screen_rejected"]:
            decisions.append({"id": r["id"], "decision": "rejected at Phase 1", "reason": "; ".join(r["reject_reasons"])})
        else:
            decisions.append({"id": r["id"], "decision": "passed Phase 1, not advanced",
                              "reason": f"rank {r['rank']} below the {MAX_TRAINED}-model training budget "
                                        f"or sound/base already represented"})
    (LAB / "results/phase1_decisions.json").write_text(json.dumps(decisions, indent=1))
    nb_train, nb_eval = [], []
    for r in chosen:
        texts = [n.rsplit(" (", 1)[0] for n in r["nearest"]]
        nb_train += texts[:2]
        nb_eval += texts[2:4]
    (SAMPLES.parent.parent / "lab_neighbours.json").write_text(json.dumps(
        {"train": sorted(set(nb_train)), "eval": sorted(set(nb_eval) - set(nb_train))}, indent=1))
    for t in trained:
        print(f"{t['id']:30s} {t['arpa_words']}  <- {t['advance_reason']}")


if __name__ == "__main__":
    main()
