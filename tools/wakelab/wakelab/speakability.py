"""Speakability / robustness metrics - reported SEPARATELY from collision.

These never offset a collision gate. They describe how easy a candidate is to
say (older adults, quiet speakers, accents) and how much acoustic "shape" it
gives a detector. Step 1 computes them; ranking by them is Step 2.
"""
from .phonetics.arpabet import (AFFRICATES, APPROXIMANTS, FRICATIVES, NASALS, PLOSIVES,
                                base, bases, is_vowel, syllable_count)

HIGH_FREQ_FRICATIVES = {"S", "Z", "SH", "ZH", "F", "TH", "V", "DH"}


def _max_cluster(pron):
    run = best = 0
    for p in pron:
        run = 0 if is_vowel(p) else run + 1
        best = max(best, run)
    return best


def _onset_class(pron):
    if not pron:
        return "empty"
    b = base(pron[0])
    if is_vowel(pron[0]):
        return "vowel"
    for name, group in (("plosive", PLOSIVES), ("affricate", AFFRICATES), ("fricative", FRICATIVES),
                        ("nasal", NASALS), ("approximant", APPROXIMANTS)):
        if b in group:
            return name
    return "other"


def metrics(pron, cfg):
    b = bases(pron)
    vowels = [p for p in b if is_vowel(p)]
    cons = [p for p in b if not is_vowel(p)]
    stress = "".join(p[-1] for p in pron if is_vowel(p) and p[-1] in "012")
    m = {
        "syllables": syllable_count(pron),
        "phonemes": len(b),
        "stress_pattern": stress,
        "distinct_consonants": len(set(cons)),
        "distinct_vowels": len(set(vowels)),
        "max_consonant_cluster": _max_cluster(pron),
        "onset": _onset_class(pron),
        "high_frequency_fricatives": sum(1 for p in b if p in HIGH_FREQ_FRICATIVES),
        "hard_phonemes": sorted({p for p in b if p in set(cfg["gates"]["hard_phonemes"])}),
    }
    notes = []
    if m["onset"] in ("vowel", "approximant"):
        notes.append("soft onset (vowel/approximant): a clipped start loses little but gives the detector a weak edge")
    if m["distinct_consonants"] <= 1:
        notes.append("few distinct consonants: little acoustic contrast")
    if m["high_frequency_fricatives"] >= 2:
        notes.append("relies on high-frequency fricatives that fade with distance and quiet voices")
    m["notes"] = notes
    return m
