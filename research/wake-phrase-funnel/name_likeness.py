"""How much an invented word looks like a real first name.

A character-trigram model trained on every US Census 1990 first name (pinned in the Wake Phrase
Lab cache). A word's score is its mean per-character log probability; it is reported as the
percentile of that score among the real names themselves. Invented words that look unlike any
real name ("pomuda", "nodula") score low; ones built like real names ("talina") score high.
Used only for the preliminary dignity/naturalness rule on constructed names.
"""
import math
from collections import Counter
from functools import lru_cache

from wakelab.corpus.registry import local_path


def _names():
    out = []
    for sid in ("census_first_female", "census_first_male"):
        for line in open(local_path(sid), encoding="utf-8"):
            parts = line.split()
            if parts:
                out.append(parts[0].lower())
    return out


def _grams(w):
    s = f"^^{w}$"
    return [(s[i - 2:i], s[i]) for i in range(2, len(s))]


@lru_cache(maxsize=1)
def _model():
    names = _names()
    tri, bi = Counter(), Counter()
    for n in names:
        for ctx, ch in _grams(n):
            tri[(ctx, ch)] += 1
            bi[ctx] += 1
    vocab = len({ch for n in names for ch in n + "$"})
    ref = sorted(_score(n, tri, bi, vocab) for n in names)
    return tri, bi, vocab, ref


def _score(w, tri, bi, vocab):
    g = _grams(w)
    return sum(math.log((tri[(c, ch)] + 1) / (bi[c] + vocab)) for c, ch in g) / len(g)


def percentile(word):
    """0-100: share of real Census first names that look LESS name-like than `word`."""
    tri, bi, vocab, ref = _model()
    s = _score(word, tri, bi, vocab)
    lo, hi = 0, len(ref)
    while lo < hi:
        mid = (lo + hi) // 2
        if ref[mid] < s:
            lo = mid + 1
        else:
            hi = mid
    return round(100 * lo / len(ref), 1)
