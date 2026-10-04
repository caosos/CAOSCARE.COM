"""Text-screen late-added mandatory candidates FOR DOCUMENTATION ONLY.

These candidates go to acoustic testing regardless of the text screen.
Results are written to results/discovery_supplemental.json; the original
Phase 1 results (results/discovery.json) are not rerun or modified.
Same engine, scoring and gates as discovery.py.

usage (from tools/wakelab with its venv): python ../../firmware/voice-pe-aria/lab/screen_supplemental.py
"""
import json

from discovery import LAB, Lab, census_share, load_config, screen_one

NOTE = "Candidate nominated by Michael for mandatory acoustic evaluation."
EXTRA = [
    {"id": "sivia (SIV-ee-uh)", "text": "sivia", "kind": "nominated", "say": "SIV-ee-uh",
     "phonemes": "S IH1 V IY0 AH0", "note": NOTE},
    {"id": "hey sivia (SIV-ee-uh)", "text": "hey sivia", "kind": "launcher", "base": "sivia (SIV-ee-uh)",
     "launcher": "hey", "say": "hey SIV-ee-uh", "phonemes": "HH EY1 S IH1 V IY0 AH0", "note": NOTE},
    {"id": "sivia (SEE-vee-uh)", "text": "sivia", "kind": "nominated", "say": "SEE-vee-uh",
     "phonemes": "S IY1 V IY0 AH0", "note": NOTE},
    {"id": "hey sivia (SEE-vee-uh)", "text": "hey sivia", "kind": "launcher", "base": "sivia (SEE-vee-uh)",
     "launcher": "hey", "say": "hey SEE-vee-uh", "phonemes": "HH EY1 S IY1 V IY0 AH0", "note": NOTE},
]


def main():
    cfg = load_config()
    lab = Lab(cfg)
    share = census_share()
    rows = []
    for c in EXTRA:
        c = {**c, "phonemes_source": "intended (screen_supplemental.py)"}
        r = screen_one(lab, share, cfg["distance"]["near"], c, {})
        r["note"] = NOTE
        r["rank"] = None
        rows.append(r)
        print(f"{r['id']:26s} rejected={r['screen_rejected']} {'; '.join(r['reject_reasons'])} "
              f"near={r['nearest'][:3]} meas={r['measurable_composite']}")
    (LAB / "results/discovery_supplemental.json").write_text(json.dumps({
        "label": "TEXT STAGE, DOCUMENTATION ONLY - these candidates are acoustically tested regardless",
        "rows": rows}, indent=1))


if __name__ == "__main__":
    main()
