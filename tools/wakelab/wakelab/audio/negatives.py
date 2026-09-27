"""Adversarial hard negatives: ordinary speech built to TRY to break a candidate.

Sources, all recorded in the run report:
1. the candidate's nearest phonetic neighbours from its `inspect` analysis
   (every metric class), each spoken bare and inside ordinary sentences;
2. hand-written "trap" lines that share the candidate's rhythm/prefix;
3. the Room 214 regression phrases (tonight's real background speech).
"""
from ..config import DOMAIN_DIR

TEMPLATES = ["{x}.", "I left it in {x}.", "Did you see {x} today?", "Well, {x}, I suppose."]

TRAPS_HEY = [
    "hey Maria", "hey Mary", "hey Harry", "hey Carrie", "hey Ari", "hey Laurie", "hey there",
    "hey everyone", "hey area", "hey, are you awake", "hey, are you there", "they are here",
    "they're all here", "hey honey", "hay area", "the bay area", "hey, how are ya",
    "hey, it's really hilarious", "he realized it", "they aired it yesterday",
]


def neighbour_texts(report, limit=30):
    """Unique neighbour texts from an inspect report's intended pronunciation."""
    judged = next(e for e in report["pronunciations"] if e["role"] != "informational")
    order = ("exact", "near", "boundary", "phrase", "domain", "clipped", "variants", "names")
    seen, out = set(), []
    for key in order:
        for f in judged["metrics"].get(key, []):
            t = f["text"]
            if f.get("private") or t in seen or t == report["candidate"]:
                continue
            seen.add(t)
            out.append((t, f"neighbour:{key}"))
    return out[:limit]


def regression_texts():
    import yaml
    with open(f"{DOMAIN_DIR}/room214_regression.yaml", encoding="utf-8") as fh:
        return [(p, "room214_regression") for p in yaml.safe_load(fh)["phrases"]]


def build(report, traps=TRAPS_HEY):
    """[(spoken_text, origin, seed_neighbour)] - bare + templated neighbours, traps, regression."""
    items = []
    for text, origin in neighbour_texts(report):
        items.append((text, origin, text))
        items += [(t.format(x=text), origin + "+sentence", text) for t in TEMPLATES[1:3]]
    items += [(t, "trap", t) for t in traps]
    items += [(t, origin, t) for t, origin in regression_texts()]
    seen, out = set(), []
    for it in items:
        if it[0].lower() not in seen:
            seen.add(it[0].lower())
            out.append(it)
    return out
