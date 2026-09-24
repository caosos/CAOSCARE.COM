"""Search index over corpus pronunciations.

Two stages keep search fast without missing close neighbours:
1. rapidfuzz pre-filter on one-char-per-phoneme strings (C++), split into
   pools by length so short items cannot flood "substring" results;
2. exact weighted alignment (align.py) on the survivors only.
"""
from rapidfuzz import fuzz, process

from ..phonetics.arpabet import bases, to_chars

TEXT, PRON, BOUNDS, PSRC, SOURCE, METRIC, CATEGORY, PER_MILLION, PRIVATE = range(9)


class CorpusIndex:
    def __init__(self, items, min_contained=3):
        self.items = items
        self.chars = [to_chars(it[PRON]) for it in items]
        self.bases = [bases(it[PRON]) for it in items]
        self.min_contained = min_contained
        self._by_len = {}
        for i, s in enumerate(self.chars):
            self._by_len.setdefault(len(s), []).append(i)

    def _pool(self, lo, hi):
        return [i for n in range(max(lo, 1), hi + 1) for i in self._by_len.get(n, ())]

    def _extract(self, query, ids, scorer, limit, cutoff):
        if not ids:
            return []
        choices = {i: self.chars[i] for i in ids}
        return [i for _, _, i in process.extract(query, choices, scorer=scorer,
                                                 limit=limit, score_cutoff=cutoff)]

    def whole_candidates(self, pron, limit, cutoff, slack=2):
        """Items of similar length that may sound like the candidate as a whole."""
        q = to_chars(pron)
        return self._extract(q, self._pool(len(q) - slack, len(q) + slack), fuzz.ratio, limit, cutoff)

    def embedding_candidates(self, pron, limit, cutoff, max_extra=24):
        """Longer items that may contain the candidate's sound somewhere inside."""
        q = to_chars(pron)
        return self._extract(q, self._pool(len(q) + 1, len(q) + max_extra),
                             fuzz.partial_ratio, limit, cutoff)

    def contained_candidates(self, pron, limit, cutoff):
        """Shorter items (>= min_contained phonemes) hidden inside the candidate."""
        q = to_chars(pron)
        return self._extract(q, self._pool(self.min_contained, len(q) - 1),
                             fuzz.partial_ratio, limit, cutoff)
