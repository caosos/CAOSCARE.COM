"""Pronunciation lookup: CMUdict first, g2p_en for words CMUdict lacks.

Every pronunciation carries its provenance ("cmudict", "g2p_en" or
"override"), because a guessed pronunciation (drug names, invented words) is
weaker evidence than a dictionary entry. Overrides pin the intended
pronunciation of a specific candidate — e.g. Michael's "Aria" = "air-ee-uh" —
and are authoritative for that candidate.
"""
import json
import os
import re

from .arpabet import parse

WORD_RE = re.compile(r"[a-z]+(?:'[a-z]+)?")


def tokenize(text):
    return WORD_RE.findall(text.lower().replace("’", "'"))


def _ensure_nltk_data():
    """g2p_en needs NLTK's POS tagger; keep it in the lab's private cache."""
    from ..config import cache_dir
    target = os.path.join(cache_dir(), "nltk_data")
    os.makedirs(target, mode=0o700, exist_ok=True)
    os.environ["NLTK_DATA"] = target
    import nltk
    if target not in nltk.data.path:
        nltk.data.path.insert(0, target)
    for pkg, kind in (("averaged_perceptron_tagger_eng", "taggers"), ("cmudict", "corpora")):
        try:
            nltk.data.find(f"{kind}/{pkg}")
        except LookupError:
            nltk.download(pkg, download_dir=target, quiet=True)


def load_cmudict(path):
    """{word: [pron, ...]} from a cmudict.dict file (variants 'word(2)')."""
    entries = {}
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.split("#", 1)[0].strip()
            if not line:
                continue
            head, *phones = line.split()
            word = re.sub(r"\(\d+\)$", "", head)
            try:
                entries.setdefault(word, []).append(parse(" ".join(phones)))
            except ValueError:
                continue
    return entries


class Lexicon:
    def __init__(self, cmudict, overrides=None, g2p_cache_path=None, allow_g2p=True):
        self.cmu = cmudict
        self.overrides = {k.lower(): [parse(p) for p in v] for k, v in (overrides or {}).items()}
        self.allow_g2p = allow_g2p
        self._g2p = None
        self._cache_path = g2p_cache_path
        self._cache = {}
        if g2p_cache_path and os.path.exists(g2p_cache_path):
            with open(g2p_cache_path, encoding="utf-8") as fh:
                self._cache = {k: tuple(v) for k, v in json.load(fh).items()}

    def word(self, w, use_g2p=None):
        """[(pron, source), ...] for one word; [] if unknown and G2P disabled."""
        w = w.lower()
        if w in self.overrides:
            return [(p, "override") for p in self.overrides[w]]
        if w in self.cmu:
            return [(p, "cmudict") for p in self.cmu[w]]
        if not (self.allow_g2p if use_g2p is None else use_g2p):
            return []
        return [(self._guess(w), "g2p_en")]

    def _guess(self, w):
        if w not in self._cache:
            if self._g2p is None:
                _ensure_nltk_data()
                from g2p_en import G2p
                self._g2p = G2p()
            self._cache[w] = tuple(p for p in self._g2p(w) if p.strip() and p not in "',.-")
        return parse(" ".join(self._cache[w]))

    def phrase(self, text, use_g2p=None, max_variants=4):
        """Pronunciations of a multi-word phrase with word-boundary offsets.

        Returns [(pron, boundaries, source)] where boundaries are the phoneme
        indices at which a new word starts; [] if any word is unknown.
        """
        if text.lower() in self.overrides:
            return [(p, (0,), "override") for p in self.overrides[text.lower()]]
        combos = [((), (), "cmudict")]
        for w in tokenize(text):
            options = self.word(w, use_g2p)
            if not options:
                return []
            combos = [(pron + p, bounds + (len(pron),), src if s == "cmudict" else s)
                      for pron, bounds, src in combos for p, s in options][:max_variants]
        return [c for c in combos if c[0]]

    def save_cache(self):
        if self._cache_path and self._cache:
            with open(self._cache_path, "w", encoding="utf-8") as fh:
                json.dump({k: list(v) for k, v in sorted(self._cache.items())}, fh)
