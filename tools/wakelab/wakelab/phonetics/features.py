"""Phoneme substitution / insertion costs - an explicit confusability model.

Why not a generic feature-distance library: PanPhon's weighted distances
were tried first (2026-09-24) and produced implausible costs for this job -
voicing pairs S/Z, T/D, P/B at 0.03, IH/IY at 0.03, while UW/OW cost 0.93.

This model is small and every number is a documented choice:
- Consonants differ by place, manner and voicing. Classic perception work
  (Miller & Nicely 1955, consonant confusions in noise) found place of
  articulation the MOST confusable feature and voicing/nasality the most
  robust, so a place-only difference is cheapest.
- Vowels differ by height, backness, rounding, diphthong glide and
  r-colouring; one step of height or backness is a small cost.
- Vowel vs consonant is maximal (1.0) except glide/vowel neighbours
  (Y~IY, W~UW, R~ER).
Costs are in [0, 1]; 1.0 = unrelated sounds. Calibration anchors are
asserted in tests/test_phonetics.py.
"""
from functools import lru_cache

from .arpabet import PHONES, VOWELS

INDEL_COST = 1.0
REDUCED_VOWEL_INDEL = 0.6   # schwa-like AH is often swallowed in casual speech

# place: 0 bilabial 1 labiodental 2 dental 3 alveolar 4 postalveolar 5 palatal 6 velar 7 glottal
CONS = {  # phone: (place, manner, voiced)
    "P": (0, "stop", 0), "B": (0, "stop", 1), "M": (0, "nasal", 1), "W": (0, "glide", 1),
    "F": (1, "fric", 0), "V": (1, "fric", 1),
    "TH": (2, "fric", 0), "DH": (2, "fric", 1),
    "T": (3, "stop", 0), "D": (3, "stop", 1), "N": (3, "nasal", 1), "S": (3, "fric", 0),
    "Z": (3, "fric", 1), "L": (3, "liquid", 1), "R": (3, "liquid", 1),
    "CH": (4, "affr", 0), "JH": (4, "affr", 1), "SH": (4, "fric", 0), "ZH": (4, "fric", 1),
    "Y": (5, "glide", 1), "K": (6, "stop", 0), "G": (6, "stop", 1), "NG": (6, "nasal", 1),
    "HH": (7, "fric", 0),
}
PLACE_STEP, PLACE_MAX = 0.12, 0.35      # place is the most confusable feature
VOICING = 0.45
MANNER = {frozenset({"stop", "affr"}): 0.35, frozenset({"fric", "affr"}): 0.35,
          frozenset({"liquid", "glide"}): 0.4, frozenset({"nasal", "stop"}): 0.55}
MANNER_DEFAULT = 0.7
SPECIAL = {frozenset({"R", "L"}): 0.4, frozenset({"F", "TH"}): 0.2, frozenset({"V", "DH"}): 0.2,
           frozenset({"M", "N"}): 0.3, frozenset({"N", "NG"}): 0.35}

# vowel: (height 0 low..3 high, back 0 front..2 back, rounded, diphthong, rhotic)
VOW = {
    "IY": (3, 0, 0, 0, 0), "IH": (2.5, 0, 0, 0, 0), "EY": (2, 0, 0, 1, 0), "EH": (1.5, 0, 0, 0, 0),
    "AE": (0.5, 0, 0, 0, 0), "AA": (0, 2, 0, 0, 0), "AO": (0.5, 2, 1, 0, 0), "OW": (1.5, 2, 1, 1, 0),
    "UH": (2.5, 2, 1, 0, 0), "UW": (3, 2, 1, 0, 0), "AH": (1, 1, 0, 0, 0), "ER": (1.5, 1, 0, 0, 1),
    "AY": (0, 1, 0, 1, 0), "AW": (0, 1, 1, 1, 0), "OY": (0.5, 2, 1, 1, 0),
}
GLIDE_VOWEL = {frozenset({"Y", "IY"}): 0.5, frozenset({"W", "UW"}): 0.5, frozenset({"R", "ER"}): 0.5}


def _cons_cost(a, b):
    if frozenset({a, b}) in SPECIAL:
        return SPECIAL[frozenset({a, b})]
    (pa, ma, va), (pb, mb, vb) = CONS[a], CONS[b]
    cost = min(PLACE_MAX, PLACE_STEP * abs(pa - pb)) if pa != pb else 0.0
    if va != vb:
        cost += VOICING
    if ma != mb:
        cost += MANNER.get(frozenset({ma, mb}), MANNER_DEFAULT)
    return min(1.0, cost)


def _vowel_cost(a, b):
    (ha, ba, ra, da, xa), (hb, bb, rb, db, xb) = VOW[a], VOW[b]
    cost = 0.2 * abs(ha - hb) + 0.2 * abs(ba - bb) + 0.1 * abs(ra - rb) + 0.25 * abs(da - db) + 0.5 * abs(xa - xb)
    return min(1.0, max(0.15, cost))


@lru_cache(maxsize=1)
def substitution_matrix():
    m = {}
    for a in PHONES:
        for b in PHONES:
            if a == b:
                m[(a, b)] = 0.0
            elif a in VOWELS and b in VOWELS:
                m[(a, b)] = _vowel_cost(a, b)
            elif a not in VOWELS and b not in VOWELS:
                m[(a, b)] = _cons_cost(a, b)
            else:
                m[(a, b)] = GLIDE_VOWEL.get(frozenset({a, b}), 1.0)
    return m


def sub_cost(a, b):
    return substitution_matrix()[(a, b)]


def indel_cost(p):
    return REDUCED_VOWEL_INDEL if p == "AH" else INDEL_COST
