"""Small, deterministic fixture corpus - no network, no cache needed.

Frequencies are illustrative (per million words), chosen to exercise the
gates; the real corpus is covered by test_real_corpus.py when built.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from wakelab.config import settings  # noqa: E402
from wakelab.phonetics.arpabet import parse  # noqa: E402

CMU = {
    "area": ["EH1 R IY0 AH0"], "aria": ["AA1 R IY0 AH0"], "that": ["DH AE1 T", "DH AH0 T"],
    "the": ["DH AH0"], "common": ["K AA1 M AH0 N"], "mary": ["M EH1 R IY0"],
    "and": ["AH0 N D"], "hello": ["HH AH0 L OW1"], "help": ["HH EH1 L P"],
    "okay": ["OW2 K EY1"], "nabu": ["N AE1 B UW0"], "zorvell": ["Z AO1 R V EH2 L"],
    "pine": ["P AY1 N"], "kay": ["K EY1"], "malaria": ["M AH0 L EH1 R IY0 AH0"],
}


def item(text, metric, per_million=None, category="x", source="fixture", private=False):
    prons, bounds = [()], [()]
    for w in text.split():
        p = parse(CMU[w][0])
        prons, bounds = [prons[0] + p], [bounds[0] + (len(prons[0]),)]
    return (text, prons[0], bounds[0], "cmudict", source, metric, category, per_million, private)


@pytest.fixture()
def cfg():
    return settings()


@pytest.fixture()
def cmudict():
    return {w: [parse(p) for p in ps] for w, ps in CMU.items()}


@pytest.fixture()
def corpus():
    items = [
        item("area", "common_word", 288.0, "word"),
        item("aria", "common_word", 2.5, "word"),
        item("hello", "common_word", 150.0, "word"),
        item("that area", "phrase", 12.0, "2-gram"),
        item("the area", "phrase", 45.0, "2-gram"),
        item("mary and", "phrase", 70.0, "2-gram"),
        item("malaria", "common_word", 12.0, "word"),
        item("common area", "domain", 20.0, "room_building", "caoscare_authored"),
        item("help", "distress", 20.0, "distress", "caoscare_authored"),
        item("okay", "domain", 20.0, "commands", "caoscare_authored"),
        item("pine", "drug", None, "drug_name", "fda_ndc"),
        item("kay", "facility", None, "facility_name", "facility_local", private=True),
    ]
    return {"items": items, "stats": {"fixture": len(items)}}
