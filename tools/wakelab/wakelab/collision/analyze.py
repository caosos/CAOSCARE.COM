"""Per-candidate collision analysis, kept as separate metrics (never one score).

A "finding" is one corpus item that sounds like the candidate:
  relation  whole     - the item as a whole sounds like the candidate
            embedded  - the candidate's sound occurs inside a longer item
            boundary  - ...and that occurrence straddles a word boundary
            contains  - a shorter item is hidden inside the candidate
  distance  normalised weighted phoneme distance (0 = identical sounds)
Metric classes come from the corpus item (common_word, phrase, domain,
distress, regression, name, drug, facility). Pronunciation variants and
clipped forms are analysed as their own metrics.
"""
import math

from ..phonetics.arpabet import bases
from ..phonetics.variants import clipped, variants
from .align import best_substring, normalized_global
from .index import BOUNDS, CATEGORY, METRIC, PER_MILLION, PRIVATE, PSRC, SOURCE, TEXT


def _finding(idx, i, relation, distance, span=None):
    it = idx.items[i]
    return {"text": "[private facility name]" if it[PRIVATE] else it[TEXT],
            "private": it[PRIVATE], "phonemes": " ".join(idx.bases[i]), "metric": it[METRIC],
            "category": it[CATEGORY], "source": it[SOURCE], "pron_source": it[PSRC],
            "per_million": it[PER_MILLION], "zipf": _zipf(it[PER_MILLION]),
            "relation": relation, "distance": round(distance, 4), "span": span, "_i": i}


def _zipf(per_million):
    return round(math.log10(per_million * 1000), 2) if per_million else None


def search(idx, pron, cfg, relations=("whole", "embedded", "contains")):
    """All findings within the near threshold for one pronunciation."""
    near = cfg["distance"]["near"]
    lim, cut = cfg["corpus"]["prefilter_limit"], cfg["corpus"]["prefilter_cutoff"]
    cand = bases(pron)
    found = {}

    def keep(f):
        key = (f["_i"], f["relation"])
        if f["distance"] <= near and (key not in found or f["distance"] < found[key]["distance"]):
            found[key] = f

    if "whole" in relations:
        for i in idx.whole_candidates(pron, lim, cut):
            keep(_finding(idx, i, "whole", normalized_global(cand, idx.bases[i])))
    if "embedded" in relations:
        for i in idx.embedding_candidates(pron, lim, cut):
            d, s, e = best_substring(cand, idx.bases[i])
            straddles = any(s < b < e for b in idx.items[i][BOUNDS])
            keep(_finding(idx, i, "boundary" if straddles else "embedded", d, [s, e]))
    if "contains" in relations:
        for i in idx.contained_candidates(pron, lim, cut):
            d, s, e = best_substring(idx.bases[i], cand)
            keep(_finding(idx, i, "contains", d, [s, e]))
    return sorted(found.values(), key=lambda f: (f["distance"], -(f["per_million"] or 0), f["text"]))


def _risk(findings, cfg):
    """Rough exposure: expected look-alike events per hour of ordinary speech.

    Counts whole-word matches and word-boundary matches only (phrases that
    merely contain a matching whole word would double-count that word).
    """
    tau, exact = cfg["distance"]["risk_tau"], cfg["distance"]["exact"]
    wph = cfg["frequency"]["words_per_hour"]
    out = {}
    for f in findings:
        if not f["per_million"] or f["relation"] not in ("whole", "boundary"):
            continue
        if f["metric"] not in ("common_word", "phrase", "domain", "distress"):
            continue
        w = 1.0 if f["distance"] <= exact else math.exp(-f["distance"] / tau)
        key = f"{f['metric']}_{f['relation']}"
        out[key] = out.get(key, 0.0) + f["per_million"] * w * wph / 1e6
    return {k: round(v, 4) for k, v in sorted(out.items())}


def analyze(idx, pron, cfg, candidate_text=""):
    """Full metric set for one pronunciation of a candidate."""
    findings = search(idx, pron, cfg)
    for f in findings:
        f["is_candidate_itself"] = f["text"].lower() == candidate_text.lower()
    base_keys = {(f["_i"], f["relation"]) for f in findings}
    var = []
    for vpron, rule, desc in variants(pron):
        for f in search(idx, vpron, cfg, relations=("whole", "embedded")):
            if (f["_i"], f["relation"]) not in base_keys:
                var.append(dict(f, variant_rule=rule, variant_desc=desc, variant_phonemes=" ".join(bases(vpron))))
    clip = []
    for cpron, label in clipped(pron):
        for f in search(idx, cpron, cfg, relations=("whole",)):
            if f["metric"] in ("common_word", "phrase", "distress"):
                clip.append(dict(f, clip=label, clipped_phonemes=" ".join(bases(cpron))))

    def pick(pred):
        return [f for f in findings if pred(f)]

    return {
        "phonemes": " ".join(pron),
        "metrics": {
            "exact": pick(lambda f: f["relation"] == "whole" and f["distance"] <= cfg["distance"]["exact"]),
            "near": pick(lambda f: f["relation"] == "whole" and f["distance"] > cfg["distance"]["exact"]),
            "phrase": pick(lambda f: f["relation"] == "embedded" and f["metric"] in ("phrase", "common_word")),
            "boundary": pick(lambda f: f["relation"] == "boundary"),
            "contains": pick(lambda f: f["relation"] == "contains"),
            "domain": pick(lambda f: f["metric"] in ("domain", "facility", "drug", "regression")),
            "names": pick(lambda f: f["metric"] in ("name", "facility")),
            "distress": pick(lambda f: f["metric"] == "distress"),
            "clipped": sorted(clip, key=lambda f: f["distance"]),
            "variants": sorted(var, key=lambda f: f["distance"]),
        },
        "risk_per_hour": _risk(findings, cfg),
    }
