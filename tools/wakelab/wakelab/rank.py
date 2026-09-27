"""Step 2: generate candidates, inspect each, keep dimensions separate, return Pareto finalists.

Doctrine (docs/WAKE_PHRASE_LAB.md): collision gates are a VETO - a candidate
that fails any gate is never a finalist, however detectable or easy to say.
Among survivors nothing is combined into one score; the report lists the
Pareto front over separate dimensions and says why each finalist is there.
"""
import datetime

from .collision.align import best_substring, normalized_global
from .corpus.registry import local_path
from .phonetics.arpabet import bases, syllable_count
from .speakability import _max_cluster

# Directive 2026-09-24: every Aria-containing candidate is tested against these.
HOSTILE_AREA = ["area", "the area", "this area", "that area", "their area", "your area",
                "our area", "dining area", "common area", "gray area", "hey area", "they area"]
ARIA_PHRASES = ["hey aria", "okay aria", "aria please", "listen aria"]
CONTROLS_GOOD = ["okay nabu", "hey mycroft", "bumblebee"]
CONTROLS_BAD = ["aria", "area", "computer", "alexa", "hey there", "excuse me", "thank you"]
NAME_EXAMPLES = ["samantha", "veronica", "penelope", "delilah", "matilda"]
STRONG_ONSET = {"plosive", "affricate", "fricative", "nasal"}
GATING = ("exact", "near", "boundary", "phrase", "domain", "names", "distress", "clipped", "variants")


def census_names(lab, max_rank=1500, syllables=(3, 4), max_zipf=3.0):
    """Conventional 3-4 syllable first names that ordinary speech rarely contains.

    Explicit, reproducible criteria (recorded in the report): census rank <=
    max_rank (a recognised human name), a CMUdict pronunciation (not a G2P
    guess), 3-4 syllables, wordfreq zipf < max_zipf (G0 would reject a more
    frequent one), no cluster > 3 consonants, no hard phonemes.
    """
    from wordfreq import zipf_frequency
    out = []
    for sid in ("census_first_female", "census_first_male"):
        with open(local_path(sid), encoding="utf-8") as fh:
            for line in fh:
                name, *_, rank = line.split()
                name = name.lower()
                if int(rank) > max_rank or name in out or name not in lab.dictionary.cmu:
                    continue
                pron = lab.dictionary.cmu[name][0]
                if not syllables[0] <= syllable_count(pron) <= syllables[1]:
                    continue
                if zipf_frequency(name, "en") >= max_zipf or _max_cluster(pron) > 3:
                    continue
                if set(bases(pron)) & set(lab.cfg["gates"]["hard_phonemes"]):
                    continue
                out.append(name)
    return out


def word_dropped(lab, text, pron):
    """Multi-word candidates: what is left if the detector loses the first or last word."""
    words = text.split()
    if len(words) < 2:
        return []
    first = len(lab.lexicon.phrase(words[0], use_g2p=True)[0][0])
    last = len(lab.lexicon.phrase(words[-1], use_g2p=True)[0][0])
    return [(pron[first:], f"'{words[0]}' lost"), (pron[:-last], f"'{words[-1]}' lost")]


def census_share():
    """name -> (percent of people with it, source) from the pinned Census files."""
    import io
    import zipfile
    out = {}
    for sid in ("census_first_female", "census_first_male"):
        with open(local_path(sid), encoding="utf-8") as fh:
            for line in fh:
                n, pct, *_ = line.split()
                out[n.lower()] = max(out.get(n.lower(), (0, ""))[0], float(pct)), "first name (% of that sex)"
    with zipfile.ZipFile(local_path("census_surnames_2010")) as z:
        name = next(n for n in z.namelist() if n.lower().endswith((".csv", ".txt")))
        for r in io.TextIOWrapper(z.open(name), encoding="latin-1").read().splitlines()[1:5001]:
            c = r.split(",")
            out.setdefault(c[0].lower(), (float(c[3]) / 1000, "surname (% of people)"))
    return out


def rare_name_only(lab, text, pron_texts, share):
    """If G4 is a candidate's ONLY failure and all its evidence is names, report how common they are."""
    rep = lab.inspect(text)
    ev = []
    for e in rep["pronunciations"]:
        if e["role"] == "informational":
            continue
        if set(e["failed_gates"]) - {"G4_domain_names_commands"}:
            return None
        for g in e["gates"]:
            if g["gate"] == "G4_domain_names_commands" and g["result"] == "FAIL":
                if any(f["metric"] != "name" for f in g["evidence"]):
                    return None
                ev += [{"name": f["text"], "distance": f["distance"],
                        "census_percent": share.get(f["text"], (None,))[0]} for f in g["evidence"]]
    return ev or None


def hostile(lab, text, prons):
    """Distance from each hostile 'area' phrase to the candidate, its clipped forms included."""
    from .phonetics.variants import clipped
    rows = []
    for phrase in HOSTILE_AREA:
        hp = bases(lab.dictionary.phrase(phrase, use_g2p=False)[0][0])
        best = None
        for pron in prons:
            forms = [(pron, "full")] + [(p, lbl) for p, lbl in clipped(pron)] + word_dropped(lab, text, pron)
            for p, form in forms:
                b = bases(p)
                for d, rel in ((normalized_global(b, hp), "whole"), (best_substring(b, hp)[0], "inside phrase")):
                    if best is None or d < best["distance"]:
                        best = {"phrase": phrase, "distance": round(d, 4), "form": form, "relation": rel}
        rows.append(best)
    return sorted(rows, key=lambda r: r["distance"])


def dimensions(report, near):
    """Separate dimensions from an inspect report (worst judged pronunciation)."""
    judged = [e for e in report["pronunciations"] if e["role"] != "informational"]
    self_zipf, neigh = 0.0, []
    for e in judged:
        for k in GATING:
            for f in e["metrics"].get(k, []):
                if f.get("is_candidate_itself") and f["metric"] in ("name", "common_word", "phrase"):
                    if f["relation"] == "whole" and f["metric"] != "name":
                        self_zipf = max(self_zipf, f["zipf"] or 0)
                    continue
                if f["relation"] == "contains":   # a word hidden INSIDE the candidate cannot wake it
                    continue
                if k == "phrase" and f["metric"] != "common_word" and f["relation"] != "boundary":
                    continue
                neigh.append({"text": f["text"], "distance": f["distance"], "metric": f["metric"],
                              "relation": f["relation"], "class": k, "zipf": f["zipf"],
                              "per_million": f["per_million"]})
    neigh.sort(key=lambda f: (f["distance"], -(f["per_million"] or 0)))
    seen, top = set(), []
    for f in neigh:
        if f["text"] not in seen:
            seen.add(f["text"])
            top.append(f)
    sp = judged[0]["speakability"]
    return {
        "candidate": report["candidate"], "verdict": report["verdict"],
        "failed_gates": sorted({g for e in judged for g in e["failed_gates"]}),
        "phonemes": [e["phonemes"] for e in judged],
        "collision_margin": top[0]["distance"] if top else None,   # None = nothing within `near`
        "risk_per_hour": round(max(sum(e["risk_per_hour"].values()) for e in judged), 4),
        "self_zipf": self_zipf,
        "syllables": sp["syllables"], "onset": sp["onset"],
        "distinct_consonants": sp["distinct_consonants"],
        "high_frequency_fricatives": sp["high_frequency_fricatives"],
        "nearest_neighbours": top[:8], "near_threshold": near,
    }


def _objectives(d):
    margin = d["collision_margin"] if d["collision_margin"] is not None else d["near_threshold"] + 0.01
    return (margin, -d["risk_per_hour"], -d["self_zipf"], d["distinct_consonants"],
            -d["high_frequency_fricatives"], 1 if d["onset"] in STRONG_ONSET else 0)


def pareto(rows):
    """Non-dominated survivors; every objective oriented so larger is better."""
    alive = [r for r in rows if not r["failed_gates"]]
    objs = {r["candidate"]: _objectives(r) for r in alive}

    def dominated(a):
        return any(all(x >= y for x, y in zip(objs[b], objs[a])) and objs[b] != objs[a]
                   for b in objs if b != a)
    return sorted((r for r in alive if not dominated(r["candidate"])),
                  key=lambda r: _objectives(r), reverse=True)


def run(lab, extra=(), names_max_rank=1500, log=print):
    cands, origin = [], {}

    def add(texts, tag):
        for t in texts:
            if t not in origin:
                cands.append(t)
                origin[t] = tag
    add(ARIA_PHRASES, "aria phrase")
    add(NAME_EXAMPLES, "name (directive example)")
    add(CONTROLS_GOOD, "control: good/neutral")
    add(CONTROLS_BAD, "control: known bad")
    add(extra, "extra")
    add(census_names(lab, names_max_rank), "name (generated)")
    near = lab.cfg["distance"]["near"]
    share = census_share()
    rows = []
    for i, text in enumerate(cands, 1):
        try:
            rep = lab.inspect(text)
        except ValueError:
            continue
        d = dimensions(rep, near)
        d["origin"] = origin[text]
        if "aria" in text.split():
            prons = [tuple(p.split()) for p in d["phonemes"]]
            d["hostile_area"] = hostile(lab, text, prons)
        if d["failed_gates"] == ["G4_domain_names_commands"]:
            d["g4_names_only"] = rare_name_only(lab, text, d["phonemes"], share)
        rows.append(d)
        if i % 20 == 0:
            log(f"  inspected {i}/{len(cands)}")
    finalists = pareto(rows)
    return {"generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "label": "TEXT STAGE ONLY - predicts danger, does not prove acoustic performance",
            "criteria": {"names_max_census_rank": names_max_rank, "name_syllables": [3, 4],
                         "name_max_zipf": 3.0, "hostile_area_phrases": HOSTILE_AREA,
                         "pareto_objectives": ["collision_margin (higher)", "risk_per_hour (lower)",
                                               "self_zipf (lower)", "distinct_consonants (higher)",
                                               "high_frequency_fricatives (lower)", "strong onset"]},
            "candidates": rows, "finalists": [r["candidate"] for r in finalists]}
