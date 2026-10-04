"""Phrase-level naming / brand risk flags - SEPARATE from licensing eligibility.

Evidence per candidate's base word (data from the Wake Phrase Lab corpus):
  known_common_word        own Zipf frequency (wordfreq English; >= 3.0 flagged)
  common_personal_name     US Census share (first-name % of that sex, or surname % of people)
  resident_staff_collision same sound as / listed in the authored senior-living name vocabulary,
                           or a same-sound spelling with census share >= 0.01%
  product_association      ONLY associations the agent knows of; each marked unverified.
                           "none known" means not known to the agent, NOT that none exists.
  pronunciation_ambiguity  more than one intended pronunciation, or the spelling's dictionary
                           reading differs from the intended sound
  spelling_ambiguity       other spellings of the same sound
  legal_review_required    always yes - no trademark or legal search has been performed

No legal or trademark conclusion is drawn here.
usage (from tools/wakelab with its venv): python ../../firmware/voice-pe-aria/lab/naming_risk.py
writes lab/results/naming_risk.json
"""
import json
import sys
from pathlib import Path

import yaml

LAB = Path(__file__).resolve().parent
sys.path.insert(0, str(LAB.parents[2] / "tools" / "wakelab"))
sys.path.insert(0, str(LAB))
from wakelab.rank import census_share  # noqa: E402

# Associations known to the agent (unverified; confirm in a trademark/product search).
KNOWN_ASSOCIATIONS = {
    "aria": "Opera's built-in browser AI assistant is named 'Aria' (agent knowledge, unverified)",
    "kestra": "Kestra is an open-source workflow-orchestration software product (agent knowledge, unverified)",
    "kookaburra": "common noun (Australian bird); used in existing brand names, e.g. sports equipment "
                  "(agent knowledge, unverified)",
    "pomona": "place name (California city, Pomona College) (agent knowledge)",
    "zaria": "place name (city in Nigeria) (agent knowledge)",
}
SPELLINGS = {
    "krysta": ["Krista", "Crista", "Christa"],
    "callista": ["Calista", "Kallista"],
    "kestra": [],
    "velora": ["Valora"],
    "aria": ["Arya (different syllable count)", "Area (AIR-ee-uh reading)"],
    "zaria": ["Zahria", "Zarya"],
    "sivia": ["Civia"],
}
# Different but close-sounding common names (evidence for resident/staff collision risk).
NEAR_NAMES = {"sivia": ["Sylvia", "Olivia", "Vivian"], "krysta": ["Chris", "Christian", "Crystal"],
              "callista": ["Melissa", "Clarissa", "Calista"], "kestra": ["Kesha"], "velora": ["Laura", "Lora"],
              "zaria": ["Maria", "Daria"], "aria": ["Maria", "Daria", "Ari"]}
MULTI_PRON = {"callista": "kuh-LISS-tuh and CALL-iss-tuh both nominated",
              "aria": "AR-ee-uh vs AIR-ee-uh (the latter = 'area')",
              "zaria": "ZAR-ee-uh vs ZAIR-ee-uh",
              "sivia": "SIV-ee-uh and SEE-vee-uh both nominated"}


def base_word(text):
    t = text.split()
    return t[-1] if t[0] in ("hey", "hi", "hello", "okay") and len(t) > 1 else text


def main():
    rows = {r["id"]: r for r in json.loads((LAB / "results/discovery.json").read_text())["rows"]}
    extra = LAB / "results/discovery_supplemental.json"
    if extra.exists():
        rows.update({r["id"]: r for r in json.loads(extra.read_text())["rows"]})
    cands = json.loads((LAB / "trained_candidates.json").read_text()) + \
        json.loads((LAB / "supplemental_candidates.json").read_text())
    share = census_share()
    names_vocab = {p.lower() for p in yaml.safe_load(open(
        LAB.parents[2] / "tools/wakelab/wakelab/corpus/domain/senior_living_negatives.yaml"))["phrases"]}
    out = {}
    for c in cands:
        b = base_word(c["text"])
        r = rows[c["id"]]
        base_row = next((x for x in rows.values() if x["text"] == b and x["kind"] != "launcher"), r)
        pct = share.get(b, (None, None))
        sp_alts = SPELLINGS.get(b, [])
        alt_share = {a: share.get(a.lower().split()[0], (None,))[0] for a in sp_alts}
        colliding = [a for a, v in alt_share.items() if v and v >= 0.01] + \
            [a for a in sp_alts if a.lower() in names_vocab]
        consistency = base_row["scores"]["measurable_text_stage"]["pronunciation_consistency"]
        out[c["slug"]] = {
            "id": c["id"], "base_word": b,
            "known_common_word": {"flag": (base_row["self_zipf"] or 0) >= 3.0, "zipf": base_row["self_zipf"]},
            "common_personal_name": {"flag": bool(pct[0] and pct[0] >= 0.01), "census_percent": pct[0],
                                     "census_list": pct[1]},
            "resident_staff_collision": {"flag": bool(colliding) or b in names_vocab,
                                         "evidence": colliding or ([b] if b in names_vocab else [])},
            "product_association": KNOWN_ASSOCIATIONS.get(b, "none known to the agent (not searched)"),
            "pronunciation_ambiguity": {"flag": b in MULTI_PRON or consistency < 10,
                                        "evidence": MULTI_PRON.get(b) or (
                                            "spelling may be read differently than intended" if consistency < 10
                                            else None)},
            "spelling_ambiguity": {"flag": bool(sp_alts), "other_spellings_same_or_near_sound": sp_alts},
            "near_sound_common_names": {n: share.get(n.lower(), (None,))[0] for n in NEAR_NAMES.get(b, [])},
            "legal_review_required": "yes - no trademark or legal search performed",
        }
    (LAB / "results/naming_risk.json").write_text(json.dumps(out, indent=1))
    for k, v in out.items():
        print(k, {x: (v[x]["flag"] if isinstance(v[x], dict) and "flag" in v[x] else v[x])
                  for x in ("known_common_word", "common_personal_name", "resident_staff_collision",
                            "pronunciation_ambiguity", "spelling_ambiguity")})


if __name__ == "__main__":
    main()
