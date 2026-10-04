"""Per-candidate scoring for the wake-phrase funnel (used by funnel.py). Deterministic.

Every field is a rule over recorded evidence (Wake Phrase Lab screen, Census, wordfreq, the
26-model calibration, authored lists.yaml). Human-factor fields (speakability, memorability,
dignity, brand) are preliminary rules for Michael's review, not judgements. See METHODOLOGY.md.
"""
import math
import sys
from pathlib import Path

from wordfreq import zipf_frequency

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "tools" / "wakelab"))

from calibrate import predict  # noqa: E402
from name_likeness import percentile  # noqa: E402

SEC_PER_PHONE, MAX_SECONDS, MIN_SYLLABLES = 0.085, 1.35, 3
RARE_NAME_PERCENT = 0.01            # same advisory policy as the 26-model lab (discovery.py)
SIBILANT = {"S", "Z", "SH", "ZH", "CH", "JH"}
WEIGHTS = {"common_speech_safety": 0.20, "similar_name_safety": 0.10, "tv_background_safety": 0.10,
           "predicted_acoustic_distinctiveness": 0.15, "senior_speakability": 0.15, "memorability": 0.10,
           "dignity_naturalness": 0.10, "brand_suitability": 0.05, "pronunciation_clarity": 0.05}


def c10(x):
    return round(max(0.0, min(10.0, x)), 1)


def bases(ph):
    return [p.rstrip("012") for p in ph.split()]


VOWELS = {"AA", "AE", "AH", "AO", "AW", "AY", "EH", "ER", "EY", "IH", "IY", "OW", "OY", "UH", "UW"}


def name_band(pct):
    if pct is None:
        return 0
    return 9 if pct >= 0.1 else 6 if pct >= RARE_NAME_PERCENT else 3


def ambiguity(c):
    a, b = bases(c["phonemes"]), bases(c["spelling_reading"])
    if a == b:
        score, why = 0, "written form reads as intended"
    elif [p for p in a if p not in VOWELS] == [p for p in b if p not in VOWELS]:
        score, why = 3, f"vowels may be read differently ({c['spelling_reading']})"
    else:
        score, why = 7, f"spelling suggests a different pronunciation ({c['spelling_reading']})"
    if c.get("base_dictionary_variants", 0) > 1:
        score, why = score + 2, why + f"; {c['base_dictionary_variants']} dictionary pronunciations"
    if c["category"] == "aria":
        score, why = max(score, 6), why + "; also spoken AIR-ee-uh = 'area' (Room 214 false wakes, 2026-09-24)"
    return min(score, 10), why


def score_one(c, s, lists, share, near, cal):
    ph = bases(c["phonemes"])
    sp = s["speakability"]
    margin, zipf = s["collision_margin"], s["self_zipf"] or 0
    common_neigh = any((n.get("zipf") or 0) >= 4 for n in s["nearest"])
    distinct_text = 10.0 if margin is None else c10(10 * margin / near)
    conv = c10(10 - 2.5 * zipf - (2 if common_neigh else 0))
    common_risk = c10(10 - (distinct_text + conv) / 2)
    names = [(e["text"], share.get(e["text"].lower(), (None,))[0]) for e in s["g4_evidence"] if e["metric"] == "name"]
    if c["category"] == "given_name":
        names.append((c["base"], c.get("census_percent")))
    worst = max([p for _, p in names if p is not None], default=None)
    name_risk = name_band(worst) if names else 0
    tv_risk = c10(10 * min(1.0, math.log10(1 + s["risk_per_hour"] * 1000) / 3))
    launcher = c["form"] == "prefix"
    pred = max(0.0, min(1.0, predict(cal, c["syllables"], len(ph), launcher, margin)))
    syl = c["syllables"]
    speak = c10(10 - (2 if syl < 3 else 0) - (2 if syl > 6 else 0) - 2 * (sp["max_consonant_cluster"] >= 3)
                - 1 * (sp["max_consonant_cluster"] == 2) - min(2, sum(p in SIBILANT for p in ph))
                - (1 if sp["onset"] in ("vowel", "approximant") else 0) - (1 if sp["hard_phonemes"] else 0))
    amb, amb_why = ambiguity(c)
    memo = {"given_name": 8, "word_name": 8, "aria": 8, "brand": 7, "role": 6, "constructed": 6, "benchmark": 8}[c["category"]]
    # Familiarity: a name/word few people know is harder to recall and to say the same way twice.
    pct = c.get("census_percent")
    unfamiliar = ((c["category"] == "given_name" and pct is not None and (2 if pct < 0.003 else 1 if pct < 0.01 else 0))
                  or (c["category"] == "word_name" and zipf_frequency(c["base"], "en") < 2.5 and 1) or 0)
    memo = c10(memo + (1 if 3 <= syl <= 5 else 0) - (2 if syl >= 7 else 0) - (1 if amb >= 7 else 0) - unfamiliar)
    base = c["base"]
    dig = {"given_name": 8, "aria": 8, "word_name": 7, "role": 7, "brand": 7, "constructed": 7, "benchmark": 2}[c["category"]]
    dig_notes = []
    if base in lists["childish_words"] or any(w in c["text"].split() for w in lists["childish_words"]):
        dig -= 5
        dig_notes.append("childish / novelty word")
    if base in lists["negative_association"]:
        dig -= 6
        dig_notes.append("strong public negative association")
    if c["category"] == "word_name" and zipf_frequency(base, "en") >= 4.5:
        dig -= 2
        dig_notes.append("everyday object word, odd as an identity")
    if c["category"] == "given_name" and syl - (2 if launcher else 0) <= 2 and base.endswith(("ie", "y")):
        dig -= 1
        dig_notes.append("diminutive form")
    if base in ("butler", "attendant", "steward", "operator"):
        dig -= 2
        dig_notes.append("servant/switchboard connotation")
    if c["category"] == "constructed":
        pct_like = percentile(base)
        cut = 3 if pct_like < 10 else 2 if pct_like < 25 else 1 if pct_like < 50 else 0
        if cut:
            dig -= cut
            dig_notes.append(f"invented word looks less name-like than {100 - pct_like:.0f}% of real first names")
    if c["category"] == "constructed" and amb >= 7:
        dig -= 1
        dig_notes.append("spelling does not show how to say it")
    embarrassing = [b for b in lists["embarrassing_substrings"] if b in base.replace(" ", "")]
    if embarrassing:
        dig = 0
        dig_notes.append(f"contains '{embarrassing[0]}'")
    known = base in lists["known_marks"]
    if known:
        brand = 1
    elif c["category"] == "given_name":
        brand = 3 if (c.get("census_percent") or 0) >= 0.1 else 5 if (c.get("census_percent") or 0) >= 0.01 else 7
    elif c["category"] == "word_name":
        brand = 3 if zipf_frequency(base, "en") >= 4 else 6
    else:
        brand = {"constructed": 8, "role": 3, "brand": 9, "aria": 1, "benchmark": 2}[c["category"]]
    tm = ["preliminary trademark / naming review required"]
    if known:
        tm.append("existing assistant or product use known to the agent (unverified)")
    if c["category"] in ("word_name", "role") and zipf_frequency(base, "en") >= 4:
        tm.append("common word: weak distinctiveness")
    if c["category"] == "given_name":
        tm.append("personal name")
    if c["category"] == "constructed":
        tm.append("invented word: clearance search needed")
    identity = {"aria": "existing identity (ARIA)", "role": "no new identity (functional)",
                "brand": "no new identity (product name)", "benchmark": "benchmark only"}.get(
        c["category"], "NEW ASSISTANT IDENTITY - would replace or sit beside ARIA; Michael's decision")
    f = {"common_speech_safety": 10 - common_risk, "similar_name_safety": 10 - name_risk,
         "tv_background_safety": 10 - tv_risk, "predicted_acoustic_distinctiveness": c10(10 * pred),
         "senior_speakability": speak, "memorability": memo, "dignity_naturalness": c10(dig),
         "brand_suitability": brand, "pronunciation_clarity": 10 - amb}
    return {
        "written_phrase": c["text"], "intended_pronunciation": c.get("say", c["text"]),
        "approx_phonemes": c["phonemes"], "syllables": syl, "stress": c["stress"],
        "category": c["category"], "form": "bare" if c["form"] == "bare" else "prefix-required" if launcher
        else c["form"], "base": base, "identity_flag": identity,
        "pronunciation_ambiguity": amb, "pronunciation_ambiguity_note": amb_why,
        "senior_speakability": speak, "memorability": memo, "dignity_naturalness": c10(dig),
        "dignity_notes": "; ".join(dig_notes), "brand_suitability": brand,
        "common_speech_collision_risk": common_risk, "similar_name_collision_risk": name_risk,
        "similar_names": ", ".join(f"{n} {p}%" if p is not None else n for n, p in names[:5]),
        "tv_background_speech_risk": tv_risk, "predicted_acoustic_distinctiveness": f["predicted_acoustic_distinctiveness"],
        "predicted_catch_rate_prior": round(pred, 3),
        "nearest_collisions": "; ".join(f"{n['text']} ({n['distance']})" for n in s["nearest"][:4]),
        "trademark_review_flag": "; ".join(tm), "gates_failed": s["failed_gates"],
        "total_preliminary_score": round(sum(WEIGHTS[k] * v for k, v in f.items()), 3),
        "mechanical_score": round((f["common_speech_safety"] + f["similar_name_safety"] + f["tv_background_safety"]
                                   + f["predicted_acoustic_distinctiveness"] + speak) / 5, 3),
        "_g4_hard": any(e["metric"] != "name" or (share.get(e["text"].lower(), (0,))[0] or 0) >= RARE_NAME_PERCENT
                        for e in s["g4_evidence"]),
        "_own_name_percent": c.get("census_percent"),
        "_embarrassing": bool(embarrassing), "_seconds": round(len(ph) * SEC_PER_PHONE, 2),
    }
