"""Acoustic batch 1 (Round 5, 2026-10-04): 8 phrases from the wake-phrase funnel's top-100 review list.

Writes batch1_candidates.json in the lab's candidate format. The phrases and the reason for each
are fixed below (the selection receipt is research/wake-phrase-funnel/batch1/SELECTION_RECEIPT.md);
phonemes are taken from the funnel's evidence file (top100_review.json) and split per word so the
lab generator can build its careful / intended / casual forms.

usage (Wake Phrase Lab venv):  python select_batch1.py
"""
import json
import sys
from pathlib import Path

LAB = Path(__file__).resolve().parent
ROOT = LAB.parents[2]
sys.path.insert(0, str(ROOT / "tools" / "wakelab"))
from wakelab.config import settings   # noqa: E402
from wakelab.inspect import Lab        # noqa: E402

LAUNCHERS = {"hey": "HH EY1", "okay": "OW2 K EY1", "hello": "HH AH0 L OW1"}
# Pronunciation corrections, recorded in the candidate file (the funnel used the CMUdict entry).
OVERRIDE = {"thomasina": ("T AA2 M AH0 S IY1 N AH0",
                          "CMUdict gives TH-; Thomasina is said tom-uh-SEE-nuh, with T as in Thomas")}
BATCH = [  # (phrase, funnel rank, reason)
    ("okay verona", 1, "word name, #1 overall; perfect text collision/TV/name safety; 3-syllable name after 'okay'"),
    ("okay evergreen", 4, "word name, #4; strong consonants (V-G-R) and a long final vowel; tests a 4-syllable compound word"),
    ("okay juniper", 14, "word name; JH and P plosives give hard acoustic edges; very easy for older speakers"),
    ("okay sequoia", 11, "word name; rare OY vowel and near-zero text collisions (9.9); tests an unusual sound pattern"),
    ("hey thomasina", 31, "real first name with 'hey' - directly comparable to the lab's Hey Callista (best natural name)"),
    ("hello home helper", 5, "role phrase, no new identity; highest predicted catch among roles; tests the 'hello' launcher"),
    ("hey care companion", 76, "role phrase, no new identity; highest predicted distinctiveness in the top 100 (6.3); "
                               "longest phrase - tests whether length buys catch rate or costs speakability"),
    ("hey nevina", 60, "best constructed (invented) name to pass the name-likeness rule; tests an invented name"),
]


def slug(s):
    return "".join(ch if ch.isalnum() else "_" for ch in s.lower()).strip("_")[:48]


def main():
    lab = Lab(settings())
    top = {r["written_phrase"]: r for r in json.loads(
        (ROOT / "research/wake-phrase-funnel/results/top100_review.json").read_text())}
    out = []
    for text, rank, reason in BATCH:
        r = top[text]
        assert r["category"] != "benchmark"
        words = text.split()
        arpa = [LAUNCHERS[words[0]]]
        for w in words[1:]:
            arpa.append(" ".join(lab.dictionary.phrase(w, use_g2p=True)[0][0]))
        if r["category"] == "constructed":           # invented word: use the funnel's intended phonemes
            arpa = [LAUNCHERS[words[0]], r["approx_phonemes"][len(LAUNCHERS[words[0]]) + 1:]]
        assert " ".join(arpa) == r["approx_phonemes"], (text, arpa, r["approx_phonemes"])
        note = None
        if words[-1] in OVERRIDE:
            arpa[-1], note = OVERRIDE[words[-1]]
        out.append({"id": text, "text": text, "slug": slug(text), "kind": r["category"], "base": r["base"],
                    "launcher": words[0], "phonemes": " ".join(arpa), "arpa_words": arpa, "pronunciation_note": note,
                    "funnel_phonemes": r["approx_phonemes"],
                    "group": "batch1 (funnel)", "funnel_rank": rank,
                    "funnel_total_preliminary_score": r["total_preliminary_score"],
                    "identity_flag": r["identity_flag"], "selection_reason": reason,
                    "funnel_senior_speakability": r["senior_speakability"],
                    "funnel_memorability": r["memorability"], "funnel_dignity": r["dignity_naturalness"]})
    (LAB / "batch1_candidates.json").write_text(json.dumps(out, indent=1))
    for c in out:
        print(c["slug"], c["arpa_words"])


if __name__ == "__main__":
    main()
