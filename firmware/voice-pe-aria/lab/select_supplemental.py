"""Supplemental mandatory candidates (Michael's correction, 2026-10-04).

The text screen was not authorised to eliminate these; they are trained and
evaluated with the identical Phase 2 procedure, beside the original 15.

Only deviation (recorded per candidate): a shared negative phrase that has the
SAME SOUND as the candidate itself (identical phoneme sequence, e.g. "Krista"
for Krysta) is excluded from that candidate's negatives, because training the
same sound as both positive and negative is a contradiction, not a test.
Near-but-different sounds (e.g. "Kestrel" for Kestra) stay as negatives.

usage (from tools/wakelab with its venv): python ../../firmware/voice-pe-aria/lab/select_supplemental.py
writes lab/supplemental_candidates.json
"""
import json
import re
import sys
from pathlib import Path

LAB = Path(__file__).resolve().parent
sys.path.insert(0, str(LAB.parents[2] / "tools" / "wakelab"))
sys.path.insert(0, str(LAB))
from wakelab.config import settings  # noqa: E402
from wakelab.inspect import Lab      # noqa: E402

from lab_common import training_negative_phrases  # noqa: E402
from select_lab import arpa_words                 # noqa: E402

MANDATORY = ["callista (kuh-LISS-tuh)", "callista (CALL-iss-tuh)", "hey callista (kuh-LISS-tuh)",
             "kestra (KESS-truh)", "hey kestra (KESS-truh)", "krysta (KRISS-tuh)", "hey krysta (KRISS-tuh)",
             # Sivia addendum (2026-10-04): rows from results/discovery_supplemental.json
             "sivia (SIV-ee-uh)", "hey sivia (SIV-ee-uh)", "sivia (SEE-vee-uh)", "hey sivia (SEE-vee-uh)"]


def bases(ph):
    return tuple(p.rstrip("012") for p in ph)


def main():
    rows = {r["id"]: r for r in json.loads((LAB / "results/discovery.json").read_text())["rows"]}
    extra = LAB / "results/discovery_supplemental.json"
    if extra.exists():
        rows.update({r["id"]: r for r in json.loads(extra.read_text())["rows"]})
    nb = json.loads((LAB / "results/lab_neighbours.json").read_text())
    negs = training_negative_phrases(nb["train"])
    lab = Lab(settings())
    neg_prons = {}
    for p in negs:
        try:
            neg_prons[p] = {bases(x) for x, _, _ in lab.dictionary.phrase(p, use_g2p=True, max_variants=4)}
        except Exception:
            neg_prons[p] = set()
    out = []
    for cid in MANDATORY:
        r = rows[cid]
        cb = bases(r["phonemes"].split())
        same = [p for p, prs in neg_prons.items() if cb in prs]
        out.append({
            "id": r["id"], "text": r["text"], "slug": re.sub(r"[^a-z0-9]+", "_", r["id"].lower()).strip("_"),
            "kind": r["kind"], "base": r.get("base"), "launcher": r.get("launcher"), "phonemes": r["phonemes"],
            "arpa_words": arpa_words(r), "phase1_rank": r["rank"], "phase1_measurable": r["measurable_composite"],
            "phase1_subjective": r["subjective_composite"], "group": "supplemental (mandatory)",
            "note": r.get("note"),
            "advance_reason": (r.get("note") or "mandatory acoustic test (Michael correction 2026-10-04)")
                              + "; text screen: "
                              + ("passed" if not r["screen_rejected"] else "; ".join(r["reject_reasons"])),
            "text_screen_nearest": r["nearest"], "text_screen_failed_gates": r["gates_failed_hard"],
            "exclude_negatives": same,
        })
        print(f"{cid:30s} exclude={same} text={'; '.join(r['reject_reasons'])[:100]}")
    (LAB / "supplemental_candidates.json").write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
