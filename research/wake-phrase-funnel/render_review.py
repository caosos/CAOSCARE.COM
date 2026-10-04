"""Write results/TOP100_REVIEW.md - Michael's review list, generated from top100_review.json and
funnel_summary.json (no hand-copied numbers).

usage: python render_review.py
"""
import json
from pathlib import Path

R = Path(__file__).resolve().parent / "results"


def main():
    s = json.loads((R / "funnel_summary.json").read_text())
    top = json.loads((R / "top100_review.json").read_text())
    o = ["# Wake-phrase funnel — top 100 for Michael's review", "",
         "Text-stage evidence and preliminary rules only: no audio was generated and no model was trained. "
         "Nothing here advances to training without Michael's approval. Scores are preliminary; human-factor "
         "columns are rules, not judgements. Hey Kookaburra appears only as an acoustic benchmark.", "",
         f"Funnel: {s['generated']} generated → {s['mechanical_survivors']} mechanical survivors → "
         f"{s['qualified_top250']} qualified → {s['human_suitable_within_qualified']} human-suitable → "
         f"{s['review_list_top100']} on this list. "
         f"{s['new_identity_in_review']} of them would introduce a new assistant identity (flagged).", "",
         "| # | Phrase | Say it | Category | Form | Identity | Score | Collision safety | Name safety | "
         "TV safety | Pred. distinct. | Speak | Memo | Dignity | Brand | Ambiguity | Nearest collisions | Similar names |",
         "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for i, r in enumerate(top, 1):
        ident = "new" if r["identity_flag"].startswith("NEW") else r["identity_flag"].split(" (")[0]
        o.append(f"| {i} | {r['written_phrase']} | {r['intended_pronunciation']} | {r['category']} | {r['form']} | "
                 f"{ident} | {r['total_preliminary_score']} | {round(10 - r['common_speech_collision_risk'], 1)} | "
                 f"{10 - r['similar_name_collision_risk']} | {round(10 - r['tv_background_speech_risk'], 1)} | "
                 f"{r['predicted_acoustic_distinctiveness']} | {r['senior_speakability']} | {r['memorability']} | "
                 f"{r['dignity_naturalness']} | {r['brand_suitability']} | {r['pronunciation_ambiguity']} | "
                 f"{r['nearest_collisions']} | {r['similar_names'] or '—'} |")
    o += ["", "## Aria family", "", "| Phrase | Status | Reason | Score |", "|---|---|---|---|"]
    for a in s["aria_family"]:
        o.append(f"| {a['written_phrase']} | {a['status']} | {a['rejection_reason'] or '—'} | "
                 f"{a['total_preliminary_score']} |")
    o += ["", "## Category distribution by stage", "", "| Stage | " + " | ".join(
        sorted(s["category_distribution"]["generated"])) + " |",
          "|---|" + "---|" * len(s["category_distribution"]["generated"])]
    for stage, dist in s["category_distribution"].items():
        o.append(f"| {stage} | " + " | ".join(str(dist.get(k, 0)) for k in sorted(
            s["category_distribution"]["generated"])) + " |")
    o += ["", "## Most common mechanical rejection reasons", ""]
    o += [f"- {k}: {v}" for k, v in s["top_mechanical_rejection_reasons"]]
    (R / "TOP100_REVIEW.md").write_text("\n".join(o) + "\n")
    print("written", len(o), "lines")


if __name__ == "__main__":
    main()
