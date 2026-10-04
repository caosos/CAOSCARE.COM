"""Phase 1 - candidate discovery screen (TEXT STAGE ONLY).

Runs every candidate in candidates.yaml (plus Hey/Hi/Hello/Okay launcher
variants of bases marked `launchers: true`) through the Wake Phrase Lab
(tools/wakelab): phonetic collision search against ~834k words, phrases,
US-Census names, drug names and authored senior-living vocabulary
(corpus/domain/*.yaml, incl. senior_living_negatives.yaml), with clipped
start/end and accent variants, then gates G0-G8. Scoring is documented in
METHODOLOGY.md. Text screening predicts danger; it does not prove acoustic
performance - criteria 6-8 (quiet / TV-on / soft-voice detection) are only
filled from Phase 2 model tests.

usage (from tools/wakelab, with its venv):
  python ../../firmware/voice-pe-aria/lab/discovery.py
writes firmware/voice-pe-aria/lab/results/discovery.{json,csv}
"""
import csv
import json
import math
import sys
from pathlib import Path

import yaml

LAB = Path(__file__).resolve().parent
sys.path.insert(0, str(LAB.parents[2] / "tools" / "wakelab"))
from wakelab.config import settings as load_config  # noqa: E402
from wakelab.inspect import Lab                     # noqa: E402
from wakelab.rank import census_share, dimensions, hostile  # noqa: E402

MAX_SECONDS = 1.35          # training clip is 1.5 s; keep the phrase inside it
SEC_PER_PHONE = 0.085       # average conversational phone duration (estimate)
RARE_NAME_PERCENT = 0.01    # G4 name-only evidence below 1 in 10,000 people is advisory
LAUNCHERS = {"hey": "HH EY1", "hi": "HH AY1", "hello": "HH AH0 L OW1", "okay": "OW2 K EY1"}
SIBILANT = {"S", "Z", "SH", "ZH", "CH", "JH"}   # whistle/lisp risk with dentures, dry mouth
PLACES = {"kalamazoo", "timbuktu", "okavango", "komodo", "zaria", "jericho", "pomona", "galileo"}
KNOWN_MARKS = {"calypso", "alexa", "okay google", "hey jarvis", "hey mycroft", "okay nabu", "computer"}


def c10(x):
    return round(max(0.0, min(10.0, x)), 1)


def bases(pron):
    return tuple(p.rstrip("012") for p in pron.split())


def expand(lab, cands):
    out = []
    for c in cands:
        c = dict(c)
        c["id"] = c.get("id", c["text"])
        if not c.get("phonemes"):
            c["phonemes"] = " ".join(lab.dictionary.phrase(c["text"], use_g2p=True)[0][0])
            c["phonemes_source"] = "dictionary/G2P"
        else:
            c["phonemes_source"] = "intended (candidates.yaml)"
        out.append(c)
        if c.get("launchers"):
            for w, ph in LAUNCHERS.items():
                out.append({"id": f"{w} {c['id']}", "text": f"{w} {c['text']}", "kind": "launcher",
                            "base": c["id"], "launcher": w, "phonemes": f"{ph} {c['phonemes']}",
                            "phonemes_source": c["phonemes_source"] + " + launcher"})
    return out


def g4_policy(rep, share):
    """G4 evidence that is only rare names (< RARE_NAME_PERCENT) is advisory, not a veto."""
    hard, rare = False, []
    for e in rep["pronunciations"]:
        if e["role"] == "informational":
            continue
        for g in e["gates"]:
            if g["gate"] == "G4_domain_names_commands" and g["result"] == "FAIL":
                for f in g["evidence"]:
                    pct = share.get(f["text"].lower(), (None,))[0]
                    if f["metric"] == "name" and (pct is None or pct < RARE_NAME_PERCENT):
                        rare.append(f"{f['text']} ({pct if pct is not None else '<census list'}%)")
                    else:
                        hard = True
    return hard, rare


def scores(c, d, sp, gates_hard, consistency):
    near = d["near_threshold"]
    margin = d["collision_margin"]
    zipf = d["self_zipf"] or 0
    common_neigh = any((n.get("zipf") or 0) >= 4 for n in d["nearest_neighbours"])
    distinct = 10.0 if margin is None else c10(10 * margin / near)
    conv = c10(10 - 2.5 * zipf - (2 if common_neigh else 0))
    tv = c10(10 * (1 - min(1.0, math.log10(1 + d["risk_per_hour"] * 1000) / 3)))
    ph = [p.rstrip("012") for p in d["phonemes"][0].split()]
    older = 10 - (2 if sp["syllables"] < 3 else 0) - (2 if sp["syllables"] > 5 else 0) \
        - 2 * (sp["max_consonant_cluster"] >= 3) - 1 * (sp["max_consonant_cluster"] == 2) \
        - 1.0 * min(2, sum(p in SIBILANT for p in ph)) - (1 if sp["onset"] in ("vowel", "approximant") else 0)
    if c["kind"] in ("aria", "word", "name", "phrase", "nominated"):
        memo = 8
    elif c["kind"] == "launcher":
        memo = 8 if "aria" in c["text"] else 7
    else:
        memo = {2: 7, 3: 6, 4: 4}.get(sp["syllables"], 3)
    if c["kind"] == "aria" and c["text"] in ("aria", "hey aria", "okay aria", "hi aria", "hello aria"):
        memo = 10
    shortened = 10 - 4 * ("G6_clipped_boundary" in d["failed_gates"]) - 3 * ("G7_accent_casual_variant" in d["failed_gates"]) \
        - (2 if sp["syllables"] < 3 else 0)
    false_wake = (distinct + conv + tv) / 3
    if gates_hard:
        false_wake = min(false_wake, 2.0)
    brand = {"invented": 9, "nominated": 8, "aria": 7, "name": 5, "word": 5, "phrase": 5,
             "launcher": 6, "control": 0}[c["kind"]]
    if c["text"] in KNOWN_MARKS or c["kind"] == "control":
        brand = 0
    elif c["text"].split()[-1] in PLACES:
        brand = min(brand, 4)
    vowel_end = ph[-1] in {"AH", "AA", "OW", "IY", "UW", "AO"}
    friendly = 6 + (2 if vowel_end else 0) + (1 if c.get("launcher") in ("hello", "hi", "hey") else 0) \
        - (2 if sp["max_consonant_cluster"] >= 3 else 0)
    return {
        "measurable_text_stage": {
            "acoustic_distinctiveness": distinct, "conversational_rarity": conv,
            "television_rarity": tv, "older_resident_pronunciation": c10(older),
            "resistance_to_shortened_pronunciation": c10(shortened),
            "false_wake_resistance": c10(false_wake), "pronunciation_consistency": consistency},
        "pending_phase2": {"quiet_room_detection": None, "television_on_detection": None,
                           "soft_voice_detection": None, "missed_wake": None, "false_positive": None},
        "subjective": {"memorability": memo, "branding_suitability": brand,
                       "emotional_friendliness": c10(friendly)},
    }


def screen_one(lab, share, near, c, seen_sound):
    """Text-screen one expanded candidate; returns its Phase 1 row."""
    rep = lab.inspect(c["text"], phonemes=c["phonemes"])
    d = dimensions(rep, near)
    judged = [e for e in rep["pronunciations"] if e["role"] != "informational"][0]
    sp = judged["speakability"]
    area = hostile(lab, c["text"], [tuple(c["phonemes"].split())])[0]
    g4_hard, g4_rare = g4_policy(rep, share)
    hard_gates = [g for g in d["failed_gates"] if g != "G4_domain_names_commands" or g4_hard]
    dict_reading = lab.dictionary.phrase(c["text"], use_g2p=True)[0][0]
    consistency = 10.0 if bases(" ".join(dict_reading)) == bases(c["phonemes"]) else 6.0
    s = scores(c, d, sp, bool(hard_gates), consistency)
    meas = s["measurable_text_stage"]
    seconds = round(sp["phonemes"] * SEC_PER_PHONE, 2)
    reasons = []
    if c["kind"] == "control":
        reasons.append("calibration control - not a product candidate")
    if hard_gates:
        reasons.append("text gates failed: " + ", ".join(hard_gates))
    if seconds > MAX_SECONDS:
        reasons.append(f"too long for the 1.5 s microWakeWord window (est. {seconds}s)")
    key = bases(c["phonemes"])
    if key in seen_sound:
        reasons.append(f"same sound as '{seen_sound[key]}' (spelling variant)")
    seen_sound.setdefault(key, c["id"])
    return {
        "id": c["id"], "text": c["text"], "kind": c["kind"], "base": c.get("base"),
        "launcher": c.get("launcher"), "say": c.get("say"), "phonemes": c["phonemes"],
        "phonemes_source": c["phonemes_source"], "dictionary_reading": " ".join(dict_reading),
        "syllables": sp["syllables"], "phonemes_count": sp["phonemes"],
        "distinct_consonants": sp["distinct_consonants"], "distinct_vowels": sp["distinct_vowels"],
        "onset": sp["onset"], "max_consonant_cluster": sp["max_consonant_cluster"],
        "est_seconds": seconds, "collision_margin": d["collision_margin"],
        "risk_per_hour_text_proxy": d["risk_per_hour"], "self_zipf": d["self_zipf"],
        "nearest": [f"{n['text']} ({n['distance']})" for n in d["nearest_neighbours"][:4]],
        "area_distance": area["distance"], "gates_failed_all": d["failed_gates"],
        "gates_failed_hard": hard_gates, "g4_rare_name_advisory": g4_rare, "scores": s,
        "measurable_composite": round(sum(meas.values()) / len(meas), 2),
        "subjective_composite": round(sum(s["subjective"].values()) / 3, 2),
        "screen_rejected": bool(reasons), "reject_reasons": reasons}


def main():
    cfg = load_config()
    lab = Lab(cfg)
    share = census_share()
    cands = expand(lab, yaml.safe_load(open(LAB / "candidates.yaml"))["candidates"])
    near = cfg["distance"]["near"]
    rows, seen_sound = [], {}
    for i, c in enumerate(cands, 1):
        rows.append(screen_one(lab, share, near, c, seen_sound))
        if i % 50 == 0:
            print(f"  screened {i}/{len(cands)}", flush=True)
    rows.sort(key=lambda r: (r["screen_rejected"], -r["measurable_composite"], -r["subjective_composite"]))
    for i, r in enumerate(rows, 1):
        r["rank"] = i
    out = LAB / "results"
    out.mkdir(exist_ok=True)
    (out / "discovery.json").write_text(json.dumps({
        "label": "PHASE 1 TEXT STAGE ONLY - predicts danger, does not prove acoustic performance",
        "corpus_stats": rep["corpus"]["stats"], "corpus_manifest": rep["corpus"]["manifest"],
        "near_threshold": near, "max_seconds": MAX_SECONDS,
        "rare_name_percent": RARE_NAME_PERCENT, "rows": rows}, indent=1))
    mk = list(rows[0]["scores"]["measurable_text_stage"])
    sk = list(rows[0]["scores"]["subjective"])
    with open(out / "discovery.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["rank", "id", "kind", "base", "launcher", "phonemes", "syllables", "phonemes_count",
                    "distinct_consonants", "distinct_vowels", "est_seconds", "measurable_composite", *mk,
                    "subjective_composite", *sk, "collision_margin", "risk_per_hour_text_proxy", "self_zipf",
                    "area_distance", "nearest", "gates_failed_hard", "g4_rare_name_advisory",
                    "screen_rejected", "reject_reasons"])
        for r in rows:
            sc = r["scores"]
            w.writerow([r["rank"], r["id"], r["kind"], r["base"] or "", r["launcher"] or "", r["phonemes"],
                        r["syllables"], r["phonemes_count"], r["distinct_consonants"], r["distinct_vowels"],
                        r["est_seconds"], r["measurable_composite"], *[sc["measurable_text_stage"][k] for k in mk],
                        r["subjective_composite"], *[sc["subjective"][k] for k in sk], r["collision_margin"],
                        r["risk_per_hour_text_proxy"], r["self_zipf"], r["area_distance"], "; ".join(r["nearest"]),
                        "; ".join(r["gates_failed_hard"]), "; ".join(r["g4_rare_name_advisory"]),
                        r["screen_rejected"], "; ".join(r["reject_reasons"])])
    print("passed:", sum(not r["screen_rejected"] for r in rows), "of", len(rows))
    for r in rows[:45]:
        print(f"{r['rank']:3d} {r['id']:30s} {r['kind']:9s} meas={r['measurable_composite']:.2f} "
              f"subj={r['subjective_composite']:.2f} margin={r['collision_margin']} {r['reject_reasons'][:1]}")


if __name__ == "__main__":
    main()
