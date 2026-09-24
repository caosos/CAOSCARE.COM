"""Assemble the collision corpus from fetched sources + authored domain lists.

Output: a list of items, each one pronunciation of one word/phrase:
  (text, pron, bounds, pron_source, source, metric, category, per_million, private)
metric is the report class: common_word | phrase | domain | distress |
regression | name | drug | facility. per_million is occurrences per million
spoken/written words where a source measures it, else None (names, drugs)
or an explicit assumed value (authored domain lists). Private facility
names are flagged and must never reach a committed file or report.
"""
import bz2
import collections
import glob
import gzip
import io
import os
import pickle
import time
import zipfile

import yaml

from ..config import DOMAIN_DIR, cache_dir, sources
from ..phonetics.lexicon import Lexicon, load_cmudict, tokenize
from .generated import numbers_dates_times
from .registry import local_path

CORPUS_FILE = "corpus_v1.pkl.gz"


def _items_for(lex, texts, *, use_g2p, source, metric, category, per_million, private=False,
               max_variants=4):
    out, missing = [], 0
    for text, pm in texts:
        prons = lex.phrase(text, use_g2p=use_g2p, max_variants=max_variants)
        if not prons:
            missing += 1
            continue
        for pron, bounds, psrc in prons:
            out.append((text, pron, bounds, psrc, source, metric, category,
                        pm if pm is not None else per_million, private))
    return out, missing


def _wordfreq(lex, cfg):
    from wordfreq import top_n_list, zipf_frequency
    words = top_n_list("en", cfg["corpus"]["wordfreq_top_n"])
    texts = [(w, 10 ** zipf_frequency(w, "en") / 1000.0) for w in words if tokenize(w) == [w]]
    return _items_for(lex, texts, use_g2p=False, source="wordfreq", metric="common_word",
                      category="word", per_million=None)


def _tatoeba(lex, cfg):
    path = local_path("tatoeba_eng")
    counts, tokens = collections.Counter(), 0
    orders = cfg["corpus"]["phrase_orders"]
    with bz2.open(path, "rt", encoding="utf-8") as fh:
        for line in fh:
            words = tokenize(line.rsplit("\t", 1)[-1])
            tokens += len(words)
            for n in orders:
                for i in range(len(words) - n + 1):
                    counts[" ".join(words[i:i + n])] += 1
    items, missing = [], 0
    for n in orders:
        ranked = sorted(((c, p) for p, c in counts.items()
                         if c >= cfg["corpus"]["phrase_min_count"] and p.count(" ") == n - 1),
                        key=lambda t: (-t[0], t[1]))[:cfg["corpus"]["phrase_max_per_order"]]
        got, miss = _items_for(lex, [(p, c / tokens * 1e6) for c, p in ranked], use_g2p=False,
                               source="tatoeba_eng", metric="phrase", category=f"{n}-gram",
                               per_million=None, max_variants=1)
        items += got
        missing += miss
    return items, missing, tokens


def _census_names(lex):
    texts = []
    for sid in ("census_first_female", "census_first_male"):
        with open(local_path(sid), encoding="utf-8") as fh:
            texts += [(line.split()[0].lower(), None) for line in fh if line.strip()]
    with zipfile.ZipFile(local_path("census_surnames_2010")) as z:
        name = next(n for n in z.namelist() if n.lower().endswith((".csv", ".txt")))
        rows = io.TextIOWrapper(z.open(name), encoding="latin-1").read().splitlines()[1:5001]
        texts += [(r.split(",")[0].lower(), None) for r in rows if r]
    texts = sorted(set(texts))
    return _items_for(lex, texts, use_g2p=True, source="census", metric="name",
                      category="common_name", per_million=None, max_variants=2)


def _fda_drugs(lex, limit=3000):
    counts = collections.Counter()
    with zipfile.ZipFile(local_path("fda_ndc")) as z:
        with z.open("product.txt") as fh:
            header = fh.readline().decode("latin-1").rstrip("\r\n").split("\t")
            cols = [header.index("PROPRIETARYNAME"), header.index("NONPROPRIETARYNAME")]
            for raw in fh:
                row = raw.decode("latin-1").rstrip("\r\n").split("\t")
                for c in cols:
                    if c < len(row):
                        counts.update(w for w in tokenize(row[c]) if len(w) > 3)
    texts = [(w, None) for w, _ in counts.most_common(limit)]
    return _items_for(lex, texts, use_g2p=True, source="fda_ndc", metric="drug",
                      category="drug_name", per_million=None, max_variants=1)


def _domain(lex, cfg):
    items, missing = [], 0
    for path in sorted(glob.glob(os.path.join(DOMAIN_DIR, "*.yaml"))):
        with open(path, encoding="utf-8") as fh:
            spec = yaml.safe_load(fh)
        got, miss = _items_for(lex, [(p, None) for p in spec["phrases"]], use_g2p=True,
                               source="caoscare_authored", metric=spec["metric"],
                               category=spec["category"],
                               per_million=cfg["corpus"]["domain_assumed_per_million"])
        items += got
        missing += miss
    got, miss = _items_for(lex, [(t, None) for t in numbers_dates_times()], use_g2p=True,
                           source="caoscare_generated", metric="domain", category="numbers_dates_times",
                           per_million=cfg["corpus"]["domain_assumed_per_million"])
    return items + got, missing + miss


def _facility(lex):
    path = local_path("facility_local")
    if not path:
        return [], 0
    with open(path, encoding="utf-8") as fh:
        names = sorted({line.strip() for line in fh if line.strip() and not line.startswith("#")})
    return _items_for(lex, [(n, None) for n in names], use_g2p=True, source="facility_local",
                      metric="facility", category="facility_name", per_million=None, private=True)


def build(cfg, log=print):
    """Build and cache the corpus (no pronunciation overrides: the corpus uses
    ordinary pronunciations; overrides apply only to the candidate)."""
    t0 = time.time()
    lex = Lexicon(load_cmudict(local_path("cmudict")),
                  g2p_cache_path=os.path.join(cache_dir(), "g2p_cache.json"))
    stats, items = {}, []
    for name, fn in (("wordfreq", lambda: _wordfreq(lex, cfg)), ("domain", lambda: _domain(lex, cfg)),
                     ("census_names", lambda: _census_names(lex))):
        got, miss = fn()
        items += got
        stats[name] = {"items": len(got), "texts_without_pronunciation": miss}
        log(f"  {name}: {len(got)} items ({miss} without pronunciation)")
    got, miss, tokens = _tatoeba(lex, cfg)
    items += got
    stats["tatoeba_phrases"] = {"items": len(got), "texts_without_pronunciation": miss,
                                "source_word_tokens": tokens}
    log(f"  tatoeba phrases: {len(got)} items from {tokens} word tokens ({miss} skipped: OOV word)")
    if os.path.exists(local_path("fda_ndc")):
        got, miss = _fda_drugs(lex)
        items += got
        stats["fda_drugs"] = {"items": len(got), "texts_without_pronunciation": miss}
        log(f"  fda drugs: {len(got)} items (G2P pronunciations)")
    got, miss = _facility(lex)
    items += got
    stats["facility_local"] = {"items": len(got), "present": bool(got)}  # count only, never names
    lex.save_cache()
    stats.update(total_items=len(items), build_seconds=round(time.time() - t0, 1))
    with gzip.open(os.path.join(cache_dir(), CORPUS_FILE), "wb") as fh:
        pickle.dump({"items": items, "stats": stats}, fh, protocol=pickle.HIGHEST_PROTOCOL)
    return stats


def load(path=None):
    with gzip.open(path or os.path.join(cache_dir(), CORPUS_FILE), "rb") as fh:
        return pickle.load(fh)
