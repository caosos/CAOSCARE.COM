# Wake-phrase funnel — methodology (2026-10-04)

Branch `research/wake-phrase-funnel` (from `772e216`, the completed 26-model Wake Word Lab).
**Text-stage research only: no audio generated, no model trained, no firmware built or flashed.**
Nothing advances to model training without Michael's approval.

## Why

The 26-model lab tested phrases picked from a smaller pool. Its best performer, Hey Kookaburra,
is acoustically strong but not acceptable as the assistant's identity. This funnel builds a much
larger pool of realistic, dignified names and short phrases and narrows it with recorded
evidence, so the next round of (expensive) training starts from candidates people could live with.

## Pipeline (deterministic; `SEED = 20261004`)

| Step | Script | Output |
|---|---|---|
| 0. Generate | `generate.py` | `results/candidates_generated.json` (1,030 product candidates + 2 benchmarks) |
| 1. Text screen | `screen.py` (Wake Phrase Lab, `tools/wakelab`) | `results/screen_raw.jsonl` |
| Calibration | `calibrate.py` (26-model lab results) | `results/calibration.json` |
| 2–3. Score + funnel | `funnel.py` (uses `score.py`) | `funnel_all.{json,csv}`, `rejected.csv`, `top250_qualified.*`, `top100_review.*`, `funnel_summary.json` |
| Report | `render_review.py` | `results/TOP100_REVIEW.md` |

Rerun: `python generate.py && python screen.py 6 && python calibrate.py && python funnel.py &&
python render_review.py` with the Wake Phrase Lab venv (`calibrate.py` needs only numpy).
`generate.py` was run twice and produced byte-identical output.

## Generation (Stage 0)

| Category | Source | Forms |
|---|---|---|
| given_name | US Census 1990 first names (female rank ≤ 2,500, all 1,219 male), CMUdict pronunciation, 2–4 syllables; 250 sampled with the seed | bare (3–4 syllables) + "hey" |
| word_name | authored list of real words used as names (`lists.yaml`) | bare + "hey" + "okay" |
| constructed | syllable grammar C-v-C-V-C-a with stress on the 2nd syllable (ve-LOR-a); excludes real words, Census names, embarrassing substrings, and spellings that read differently (c/g before e/i); 190 sampled with the seed | bare + "hey" |
| role | functional phrases (companion, concierge, front desk …) — no new identity | "hey"/"okay"/"hello" only |
| brand | CAOSCare phrases ("hey caos", "caos care" …), "caos" pinned as kay-oss | as written |
| aria | Aria, Hey/Okay/Hello/Hi Aria, Aria please, Aria listen, Hey there Aria — pinned AR-ee-uh | as written |
| benchmark | hey kookaburra, kookaburra — **acoustic reference only, never a product candidate** | — |

Bare and prefixed forms are separate candidates, screened and scored separately.

## Recorded per candidate

Written phrase; intended pronunciation; approximate phonemes (ARPAbet); syllables and stress;
bare or prefix-required; identity flag; pronunciation ambiguity; senior speakability; memorability;
dignity/naturalness; brand suitability; common-speech collision risk; similar-name collision risk;
TV/background-speech risk; predicted acoustic distinctiveness; preliminary trademark/naming flag;
pass/fail; rejection reason; total preliminary score. Plus nearest colliding words/phrases and
similar names with their Census share.

## Measurable fields (from the Wake Phrase Lab screen)

The screen compares each candidate's intended phonemes against an 834,030-item phonetic corpus
(CMUdict words, frequent phrases, Census names, drug names, senior-living vocabulary), including
clipped starts/ends and accent/casual variants, and applies gates G0–G8.

- **Common-speech collision risk (0–10, higher = worse)** = 10 − mean(text distinctiveness,
  conversational rarity). Distinctiveness = 10 × collision margin / 0.25 (10 if nothing within
  0.25). Rarity = 10 − 2.5 × the phrase's own Zipf frequency − 2 if a near neighbour is a common
  word (Zipf ≥ 4).
- **Similar-name collision risk** from the Census share of the names behind G4 evidence (and the
  candidate itself if it is a first name): none 0; < 0.01% 3; 0.01–0.1% 6; ≥ 0.1% 9.
- **TV/background-speech risk** = 10 × min(1, log10(1 + text-proxy false wakes/h × 1000) / 3), from
  the lab's corpus-frequency estimate. A text proxy, not a measurement.
- **Predicted acoustic distinctiveness** = 10 × a prior catch rate from `calibration.json`: a linear
  fit of the 26 models' measured catch rate on syllables, phoneme count, launcher and collision
  margin (in-sample R² 0.47, leave-one-out error ±0.12). n = 26 and synthetic voices: it orders
  candidates for testing; it is not a predicted real-room catch rate. The lab also showed launcher
  forms reached the simulated ambient limit more often (7/13) than bare forms (4/13).
- **Pronunciation ambiguity**: intended phonemes vs how the written form is read (dictionary/G2P):
  identical 0; same consonants, vowels may differ 3; different 7; +2 for more than one dictionary
  pronunciation; Aria family at least 6 (spoken both AR-ee-uh and AIR-ee-uh = "area", the Room 214
  false wakes of 2026-09-24).

## Preliminary human-factor rules (for review — not judgements)

- **Senior speakability**: starts at 10; −2 under 3 or over 6 syllables, −2 a 3-consonant cluster,
  −1 a 2-consonant cluster, −1 per sibilant (max −2; dentures/dry mouth), −1 soft vowel/approximant
  start, −1 a hard phoneme.
- **Memorability**: real names/words 8, brand 7, role and constructed 6; +1 for 3–5 syllables,
  −2 for ≥ 7, −1 if the spelling suggests a different sound; unfamiliarity −1/−2 (first name under
  0.01% / 0.003% of people; a word with Zipf < 2.5).
- **Dignity / naturalness**: first names and Aria 8, word names/role/brand/constructed 7;
  −5 childish/novelty word, −6 strong public negative association, −2 everyday object word
  (Zipf ≥ 4.5), −1 diminutive first name, −2 servant/switchboard connotation (butler, attendant,
  steward, operator), −1 an invented word whose spelling does not show how to say it, and for
  invented words a name-likeness penalty (`name_likeness.py`: a character-trigram model of all
  Census first names; percentile among real names < 10 → −3, < 25 → −2, < 50 → −1); an
  embarrassing substring sets 0 and rejects.
- **Brand suitability**: known assistant/product name (agent knowledge, unverified) 1; first name
  by commonness 3/5/7; common word 3, other word 6; constructed 8; role 3; CAOSCare brand 9.
- **Trademark / naming flag**: always "preliminary review required", plus the specific concern. No
  legal conclusion is drawn.
- **Identity flag**: any personal/word/invented name is flagged "NEW ASSISTANT IDENTITY — would
  replace or sit beside ARIA; Michael's decision". Role and brand phrases introduce no new identity.

## Funnel

1. **Mechanical gates (any failure rejects):** benchmark; embarrassing substring; Wake Phrase Lab
   hard gates (a G4 failure caused only by names under 0.01% of people is advisory — the 26-model
   lab's policy); own first name ≥ 0.1% of people (likely a resident's or staff member's name);
   estimated duration > 1.35 s (0.085 s/phoneme; the detector window is 1.5 s); fewer than 3
   syllables; same sound as an earlier candidate. Survivors are ordered by **mechanical score**
   (mean of collision, name and TV safety, predicted distinctiveness, speakability); the best 250
   form the **qualified list**.
2. **Human suitability:** dignity ≥ 7, memorability ≥ 6, speakability ≥ 6, brand ≥ 3, ambiguity ≤ 4.
   Survivors are ordered by **total preliminary score**; the best 100 form the **review list**.
3. Ties break alphabetically by phrase. Bare and prefixed forms compete as separate rows.

**Total preliminary score** = 0.20 common-speech safety + 0.10 similar-name safety + 0.10 TV
safety + 0.15 predicted distinctiveness + 0.15 senior speakability + 0.10 memorability + 0.10
dignity + 0.05 brand + 0.05 pronunciation clarity (safety = 10 − risk; clarity = 10 − ambiguity).
Aria phrases receive no special treatment.

## Limits

- Everything is text-stage. Collision, TV and name risk come from phonetic comparison and corpus
  frequency, not from audio. The 26-model lab showed the text screen can over-penalise launcher
  phrases with names (Hey Callista, Hey Krysta), so advisory gates stay advisory.
- Human-factor scores are rules over simple signals. Michael's review is the real test.
- Brand and trademark flags use the agent's knowledge only; no search was performed.
- Any model later trained for these phrases inherits the lab's licensing gate unless it is
  trained on commercially licensed data.
