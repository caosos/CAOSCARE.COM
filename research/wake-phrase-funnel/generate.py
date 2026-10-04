"""Stage 0 - deterministic candidate generation (no audio, no training).

Builds >= 1,000 wake names / short phrases from five reproducible sources and writes
results/candidates_generated.json. Same inputs + same SEED -> byte-identical output.

  given_name   real first names from the pinned US Census 1990 lists (CMUdict pronunciation)
  word_name    authored real words used as names (lists.yaml)
  constructed  name-like words built from a fixed syllable grammar, deterministic sample
  role         functional phrases that address the system by role (no new identity)
  brand        CAOSCare product phrases
  aria         the Aria family, kept as a category (no special scoring)
  benchmark    acoustic benchmarks only (hey kookaburra) - never product candidates

usage: run with the Wake Phrase Lab venv from this directory:  python generate.py
"""
import json
import random
import sys
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "tools" / "wakelab"))
from wakelab.config import settings          # noqa: E402
from wakelab.corpus.registry import local_path  # noqa: E402
from wakelab.inspect import Lab               # noqa: E402

SEED = 20261004
LAUNCHER = {"hey": "HH EY1", "okay": "OW2 K EY1", "hello": "HH AH0 L OW1", "hi": "HH AY1"}
ARIA = "AA1 R IY0 AH0"                         # AR-ee-uh (Michael 2026-10-03), not "area"
N_GIVEN, N_CONSTRUCTED = 250, 190

# Constructed-name grammar: C1 v1 C2 V2 C3 a, stress on V2 (ve-LOR-a, ta-LIN-a).
ONSET = [("b", "B"), ("c", "K"), ("d", "D"), ("f", "F"), ("g", "G"), ("l", "L"), ("m", "M"),
         ("n", "N"), ("p", "P"), ("r", "R"), ("s", "S"), ("t", "T"), ("v", "V"), ("z", "Z")]
V1 = [("a", "AH0"), ("e", "EH0"), ("o", "OW0")]
MID = [("l", "L"), ("r", "R"), ("n", "N"), ("m", "M"), ("v", "V"), ("d", "D"), ("t", "T")]
V2 = [("a", "AA1"), ("e", "EH1"), ("i", "IY1"), ("o", "OW1"), ("u", "UW1")]
CODA = [("n", "N"), ("r", "R"), ("l", "L"), ("t", "T"), ("v", "V"), ("d", "D"), ("s", "S")]


def syllables(ph):
    return sum(p[-1].isdigit() for p in ph.split())


def stress(ph):
    return "-".join(p[-1] for p in ph.split() if p[-1].isdigit())


def census_names():
    out = {}
    for sid, max_rank in (("census_first_female", 2500), ("census_first_male", 1219)):
        for line in open(local_path(sid), encoding="utf-8"):
            parts = line.split()
            if len(parts) == 4 and int(parts[3]) <= max_rank:
                out.setdefault(parts[0].lower(), float(parts[1]))
    return out


def row(text, phonemes, category, form, base, **kw):
    return {"id": text, "text": text, "phonemes": phonemes, "category": category, "form": form,
            "base": base, "syllables": syllables(phonemes), "stress": stress(phonemes), **kw}


def with_prefixes(base_rows, prefixes):
    out = []
    for r in base_rows:
        for p in prefixes:
            out.append(row(f"{p} {r['text']}", f"{LAUNCHER[p]} {r['phonemes']}", r["category"],
                           "prefix", r["base"], say=f"{p} {r.get('say', r['text'])}",
                           phonemes_source=r["phonemes_source"] + " + launcher"))
    return out


def main():
    lists = yaml.safe_load(open(HERE / "lists.yaml"))
    lab = Lab(settings())
    cmu = lab.dictionary.cmu
    rng = random.Random(SEED)
    bad = [s for s in lists["embarrassing_substrings"]]
    rows = []

    # Aria family (preserved category)
    for a in lists["aria_phrases"]:
        ph = " ".join(LAUNCHER[w] if w in LAUNCHER else ARIA if w == "aria" else
                      " ".join(lab.dictionary.phrase(w, use_g2p=True)[0][0]) for w in a["text"].split())
        rows.append(row(a["text"], ph, "aria", a["form"], "aria", say=a["text"].replace("aria", "AR-ee-uh"),
                        phonemes_source="pinned AR-ee-uh"))

    # Given names: Census, CMUdict pronunciation, 2-4 syllables, deterministic sample
    share = census_names()
    pool = sorted(n for n in share if n in cmu and 2 <= syllables(" ".join(cmu[n][0])) <= 4
                  and not any(b in n for b in bad) and n != "aria")
    picked = sorted(rng.sample(pool, min(N_GIVEN, len(pool))))
    given = [row(n, " ".join(cmu[n][0]), "given_name", "bare", n, census_percent=share[n],
                 phonemes_source="cmudict", cmu_variants=len(cmu[n])) for n in picked]
    rows += [g for g in given if g["syllables"] >= 3] + with_prefixes(given, ["hey"])

    # Real words used as names
    words = []
    for w in lists["word_names"]:
        ph = lab.dictionary.phrase(w, use_g2p=True)[0]
        words.append(row(w, " ".join(ph[0]), "word_name", "bare", w, phonemes_source=ph[2],
                         cmu_variants=len(cmu.get(w, [])) or 1))
    rows += words + with_prefixes(words, ["hey", "okay"])

    # Constructed names
    pool = []
    for (c1, p1) in ONSET:
        for (v1, q1) in V1:
            for (c2, p2) in MID:
                for (v2, q2) in V2:
                    for (c3, p3) in CODA:
                        if c2 == c3 or c1 == c2 or (c1 in "cg" and v1 in "ei"):
                            continue
                        sp = f"{c1}{v1}{c2}{v2}{c3}a"
                        if sp in cmu or sp in share or any(b in sp for b in bad):
                            continue
                        q2s = "AO1" if (v2 == "o" and c3 == "r") else q2
                        pool.append((sp, f"{p1} {q1} {p2} {q2s} {p3} AH0"))
    cons = [row(sp, ph, "constructed", "bare", sp, phonemes_source="intended (syllable grammar)",
                say=sp) for sp, ph in sorted(rng.sample(sorted(pool), N_CONSTRUCTED))]
    rows += cons + with_prefixes(cons, ["hey"])

    # Role phrases (no new identity) - prefix required
    roles = []
    for w in lists["role_words"]:
        ph = lab.dictionary.phrase(w, use_g2p=True)[0]
        roles.append(row(w, " ".join(ph[0]), "role", "bare", w, phonemes_source=ph[2]))
    rows += with_prefixes(roles, lists["role_prefixes"])

    # Brand phrases
    for b in lists["brand_phrases"]:
        rows.append(row(b["text"], b["phonemes"], "brand", "prefix" if b["text"].split()[0] in LAUNCHER
                        else "bare", "caos", phonemes_source="pinned (kay-oss)", say=b["text"]))

    # Benchmarks (never product candidates)
    for t in lists["benchmarks"]:
        ph = " ".join(" ".join(lab.dictionary.phrase(w, use_g2p=True)[0][0]) for w in t.split())
        rows.append(row(t, ph, "benchmark", "prefix" if t.startswith("hey") else "bare", "kookaburra",
                        phonemes_source="cmudict"))

    seen, out = set(), []
    for r in rows:                       # unique written phrases, first occurrence wins
        if r["id"] not in seen:
            seen.add(r["id"])
            # How a reader would say the written form (dictionary / G2P), for ambiguity checks.
            r["spelling_reading"] = " ".join(lab.dictionary.phrase(r["text"], use_g2p=True)[0][0])
            r["base_dictionary_variants"] = len(cmu.get(r["base"], []))
            out.append(r)
    (HERE / "results").mkdir(exist_ok=True)
    (HERE / "results/candidates_generated.json").write_text(json.dumps(
        {"seed": SEED, "count": len(out), "product_candidates": sum(r["category"] != "benchmark" for r in out),
         "candidates": out}, indent=1))
    from collections import Counter
    print(len(out), Counter(r["category"] for r in out), Counter(r["form"] for r in out))


if __name__ == "__main__":
    main()
