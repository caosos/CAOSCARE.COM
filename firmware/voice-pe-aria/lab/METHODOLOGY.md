# CAOSCare Wake Word Lab — methodology

**Purpose:** find the strongest CAOSCare wake word or phrase by evidence. The
assistant identity stays ARIA; the product is not renamed here.

**Scope:**
- Synthetic testing only ranks candidates.
- **The final choice requires physical Voice PE testing**
  (`device_test/PHYSICAL_TEST_SHEET.md`).
- No winner is picked from written guidance.

**Inputs that shaped this study** (Michael, 2026-10-03/04):
- the controlled-candidate request (Aria, Hey Aria, Aria Care, Okay Aria,
  Zaria, Hey Zaria);
- the discovery study (100+ candidates, phases 1–3);
- the Google research addendum (3–4 syllables; T/K/P/J/G/D/Z; measure, don't
  assume, a launcher's effect);
- the expanded discovery input (18 nominated names, launcher variants,
  resident-specific conditions, the senior-living confusion list).

## Phase 1 — discovery and text screening (`discovery.py`)

**Candidate pool** (`candidates.yaml`): 183 base entries plus Hey / Hi / Hello
/ Okay launcher variants for 55 bases, **403 in total**. Families:
- Aria variants;
- invented 2-, 3- and 4-syllable words;
- invented words with strong K/T/P/B/D/G/J/Z onsets and internal
  ST/SK/KR/TR/KT;
- older-voice designs (open vowels, voiced, no sibilants);
- real words with strong internal sound changes;
- short natural phrases;
- uncommon 3- and 4-syllable human names;
- the 18 names Michael nominated, with his stated pronunciations;
- calibration controls (Alexa, Okay Google, Hey Jarvis, Hey Mycroft,
  Computer, Okay Nabu). Controls are screened, never advanced.

**Pronunciation:**
- Every invented or nominated word carries an explicit intended ARPAbet
  pronunciation, so spelling can't change the sound.
- Spelling variants with the same sound ("Krysta" / "Krista") are treated as
  one acoustic candidate. Later duplicates are rejected as "same sound".

**Screening engine:** the existing Wake Phrase Lab
(`tools/wakelab`, see `docs/WAKE_PHRASE_LAB.md`).
- **Corpus:** a phonetic collision search over 834,030 items:
  - CMUdict;
  - wordfreq English, whose blend includes OpenSubtitles — used as the
    TV/film dialogue frequency proxy;
  - Tatoeba sentences;
  - US Census first names and surnames;
  - FDA drug names;
  - authored senior-living vocabulary, including
    `senior_living_negatives.yaml`: Michael's required words, the direct
    confusion list, staff/resident names, nursing, dining, activities,
    maintenance, transportation, telephone, weather and news phrases, and
    medication names.
- **Variants:** each candidate is also checked in clipped-start, clipped-end,
  accent and casual forms.
- **Gates** (a failed gate rejects):
  - G0 the candidate itself is common;
  - G1 exact common word;
  - G2 near a high-frequency word;
  - G3 embedded in or containing a common word;
  - G4 near senior-living vocabulary, commands or a common name;
  - G5 distress vocabulary;
  - G6 a clipped form collides;
  - G7 an accent or casual variant collides;
  - G8 speakability.
- **G4 name policy (documented exception):** if all of a candidate's G4
  evidence is human names that each occur in fewer than 1 in 10,000 people
  (US Census), G4 is advisory, not a veto. Senior-living vocabulary always
  stays a hard veto.
- **Length:** the estimated spoken length must fit the 1.5 s microWakeWord
  window (≤ 1.35 s at 85 ms per phoneme).

**Scores, 0–10.** Measurable scores rank candidates; subjective scores are
reported but never used for ranking.

| Score | Type | Formula / rubric |
|---|---|---|
| acoustic distinctiveness | measurable (text proxy) | 10 × nearest-collision distance ÷ "near" threshold (10 if nothing is near) |
| conversational rarity | measurable | 10 − 2.5 × the candidate's own Zipf frequency − 2 if a neighbour has Zipf ≥ 4 |
| television rarity | measurable (proxy) | from the lab's frequency-weighted collision risk per hour (wordfreq includes subtitles) |
| older-resident pronunciation | measurable | 10, minus penalties: < 3 or > 5 syllables; 3-consonant clusters (−2) and 2-clusters (−1); each sibilant (dentures / dry-mouth whistle), up to 2; vowel or approximant onset (−1) |
| resistance to shortened pronunciation | measurable | 10 − 4 if a clipped form collides (G6) − 3 if a casual or accent form collides (G7) − 2 if < 3 syllables |
| false-wake resistance | measurable | mean of the three rarity/distinctiveness scores; capped at 2 if any hard gate fails |
| pronunciation consistency | measurable | 10 if the dictionary/G2P reading of the spelling equals the intended sound, else 6 (spelling likely to be misread) |
| memorability | subjective | Aria family 10; real word, name or phrase 8; invented 2-syllable 7, 3-syllable 6, 4-syllable 4 |
| branding suitability | subjective | invented 9; nominated name 8; Aria family 7; launcher phrase 6; word or name 5; places ≤ 4; known assistant trademarks 0 (no trademark search performed) |
| emotional friendliness | subjective | 6, +2 for an open-vowel ending, +1 for a hey/hi/hello launcher, −2 for 3-consonant clusters |
| quiet-room / TV-on / soft-voice detection, missed-wake, false-positive performance | **measured in Phase 2** | from the trained models |

Also reported per candidate: total syllables, total phonemes, distinct
consonants (consonant distinctiveness), distinct vowels (vowel variation),
nearest sound-alikes, and distance to "area"-type phrases.

## Phase 1 → 2 advancement (`select_lab.py`)

At most 15 models; every decision is recorded in
`results/phase1_decisions.json`.

- **A.** Michael's comparison baselines: Aria, Hey Aria, Zaria. Trained even
  though the text screen rejected them.
- **B.** First-request Aria variants that pass the text screen. Okay Aria
  passes; Aria Care and Hey Zaria were rejected, with reasons recorded.
- **C.** For each family — invented, invented with ST/SK/KR/TR/KT, real word —
  the best passing base plus its best passing launcher. A prefix's effect is
  **measured** by training both.
- **D.** Michael's nominated names and human names: the best passing launcher
  phrase plus its bare name. The bare name is trained even if the text screen
  rejected it, so the launcher effect is measured.
- **F.** Fill to 15 with the next best passing base.

## Phase 2 — identical acoustic model testing

Configuration lives in `lab_common.py`; the code is `gen_lab.py`,
`train_lab.py`, `eval_lab.py`, `report_lab.py` and `eval_data_prep.py`.

**Identical for every candidate:**
- seeds (`SEED = 20261003`; per-clip and per-set seeds derived from it);
- 1,800 positive clips: 3 pronunciation forms × 600;
- one shared negative feature set, built once and reused byte-identically by
  every model;
- generator settings (length scales 0.8–1.25, noise scales);
- augmentation (MIT RIRs, FMA + AudioSet backgrounds, −5…10 dB SNR);
- the microWakeWord recipe: mixednet, 10,000 steps, batch 128, negative
  class weight 20;
- the evaluation clips, conditions, ambient streams, cutoffs and detection
  rule.

**Evaluation determinism (corrected 2026-10-04).** Every model is evaluated on
the same clip files, and each (clip, condition) pair gets the same noise
segment and augmentation draws: the per-clip seed is
`SEED + crc32("<path relative to samples/lab/eval>|<condition>")`. The
ambient streams are fixed files scored without randomness. The first full run
used Python's `hash()` for this seed; `hash()` is salted per process, so each
model received different noise offsets and augmentation draws. All 26
evaluations and cross-checks were re-run with the deterministic seed (no
retraining, `rerun_eval_deterministic.sh`); the earlier outputs are kept in
each run's `superseded_2026-10-04_salted_seed/` folder.

**Positives** are synthesised from each candidate's **exact phonemes** with
the LibriTTS-R generator, in three forms:
- careful: all vowels full;
- intended;
- casual: unstressed vowels reduced, final vowel shortened.

**Shared training negatives** (98 phrases + 24 Phase 1 neighbours, 50 clips
each):
- Michael's required list: area, care, caregiver, Maria, Daria, Ari, Ariel,
  Victoria, malaria, "hey Maria", "hey Ari", family, therapy, dietary,
  activities, emergency, maintenance, transportation, nurse, light,
  television, call, help;
- the direct confusion list: Krista, Crystal, Chris, Christian, Christmas,
  Clarissa, Melissa, Cassandra, Calista, Kestrel, extra, list, listen, very,
  various;
- launcher-only phrases ("hey", "hello there", "okay then", …);
- general room, TV and staff phrases;
- each trained candidate's two nearest Phase 1 sound-alikes;
- plus the microWakeWord speech, dinner-party and no-speech negative features.

**Held-out evaluation set (never trained on):**
- 24 named speakers from 17 Piper VITS voices: US and GB, male and female,
  accented L2-ARCTIC, the "gloomy" SEMAINE voice and the deep ARCTIC rms
  voice. Real elderly, Southern-US and denture speech are **not available**
  synthetically; those effects are only simulated (below).
- positives of every candidate at 2 speeds;
- AIR-ee-uh ("area-like") renditions of the Aria/Zaria family, for
  pronunciation sensitivity;
- all shared negatives;
- 22 held-out Phase 1 sound-alikes;
- 20 held-out TV/news/room sentences.

**Clip conditions** (`eval_lab.py`):
- clean; −18 dB and −30 dB (low volume);
- simulated room at 1, 2 and 4 m (2 m is the "quiet room");
- bed / facing away (3 m + head-shadow low-pass);
- TV on (2 m + TV-dialogue proxy at 5 dB SNR);
- another talker nearby (0 dB SNR);
- HVAC, music and room background (10 / 5 / 10 dB);
- weak first consonant (first 150 ms faded in);
- shortened final syllable (last 20% removed);
- syllables run together (1.3× time compression);
- older-voice simulation (−2 semitones, 0.9× tempo);
- raspy simulation (breath noise + mild distortion);
- denture simulation (smeared 4–8 kHz band).

Positives use all conditions; negatives use clean, −18 dB, 2 m, TV on and
nearby talker.

**Ambient false activations per hour**, streamed continuously with a 2 s
refractory:
- TV-dialogue proxy: LibriSpeech, 2.8 h;
- music: FMA, 1 h;
- room background: DEMAND, 20 min;
- HVAC (procedural): 1 h;
- silence: 0.5 h;
- plus DiPCo dinner-party room conversation (5.3 h), from the microWakeWord
  test split.

**Detection rule:** the ESPHome micro_wake_word rule. The mean of 5
consecutive 30 ms probabilities must exceed the cutoff; every cutoff from 0.20
to 0.99 is stored.

**Operating points reported:**
- fixed: 0.90 for every model;
- **matched:** each model's most sensitive cutoff with ≤ 0.5 ambient false
  activations per hour. This is the fairest side-by-side comparison.

**Hardware figures:**
- TFLite-Micro arena (RAM) and model bytes (flash);
- host inference time per step (no device measurement possible);
- detection latency from the end of speech.

## Phase 3 — finalists (`recommend_lab.py`, revised 2026-10-04)

**Licensing is a hard gate, not a score.** Every current model was trained
with non-commercial material. Each one is therefore:
- **RESEARCH ONLY**;
- **NOT COMMERCIALLY RELEASABLE**;
- given no ranking points for licensing;
- never presented as shipping firmware.

**Weighted score (0–10).** Weights were fixed before results. Every raw factor
value is reported so Michael can re-weight later.

| Factor | Weight | Type |
|---|---|---|
| true-wake performance (matched-point TPR, all conditions) | 0.30 | acoustic, measured |
| false-wake performance (confusion false-activation rate at the matched point; 0 if the model can't reach ≤ 0.5 ambient false activations per hour) | 0.30 | acoustic, measured |
| older-resident usability: 0.7 × measured TPR on the resident conditions + 0.3 × Phase 1 text score | 0.20 | measured + text |
| memorability | 0.10 | **human-factors judgement** |
| natural assistant identity | 0.10 | **human-factors judgement** |

**Naming / brand risk is a separate flag set** (`naming_risk.py` →
`results/naming_risk.json`). It is never scored, and never presented as
licensing eligibility. It records:
- known common word, with Zipf evidence;
- common personal name (US Census share);
- likely resident/staff name collision;
- existing assistant or product association (only associations known to the
  agent, marked unverified);
- pronunciation ambiguity;
- spelling ambiguity;
- "legal review required: yes" for every candidate.

No trademark or legal conclusion is drawn.

**Selection:**
- Ranking is by weighted score; an exact tie is broken by candidate id
  (alphabetical), so the order is deterministic.
- The five finalists are the top five by weighted score, at most one variant
  per base word. Launcher forms and pronunciation variants of one word compete
  only with each other, so they cannot crowd a different word off the list;
  the variants passed over are listed in `recommendation.json`
  (`skipped_same_base_before_five_filled`).
- Natural-identity points: 10 only when the base word is "aria" itself (the
  assistant's name); a name that merely contains "aria" (Zaria) scores as a
  name (7). Corrected 2026-10-04 — the first ranking used a substring test.
- The three physical-test finalists are the top three of those five. At least
  one must be a memorable natural name (memorability ≥ 8), if any such model
  meets minimum acoustics: matched TPR ≥ 0.6, confusion rate ≤ 0.1 and ≤ 0.5
  ambient false activations per hour.

**Supplemental mandatory candidates** (Michael, 2026-10-04): Callista
(kuh-LISS-tuh and CALL-iss-tuh), Hey Callista, Kestra, Hey Kestra, Krysta,
Hey Krysta.
- Trained and evaluated with the identical procedure and reported beside the
  original 15.
- The original 15's results are never rewritten; their cross-check on the
  supplemental speech goes to a separate file.
- **The only deviation:** a shared negative phrase with exactly the same sound
  as the candidate ("Calista" for Callista kuh-LISS-tuh, "Krista" for Krysta)
  is excluded from that candidate's negatives. Training the same sound as both
  positive and negative is a contradiction, not a test. Recorded in each
  model's `training_parameters.yaml`.

**Sivia addendum** (2026-10-04). "Candidate nominated by Michael for
mandatory acoustic evaluation."

Four models are trained with the identical procedure:
- Sivia (SIV-ee-uh)
- Hey Sivia (SIV-ee-uh)
- Sivia (SEE-vee-uh)
- Hey Sivia (SEE-vee-uh)

**Text screen:** done for documentation only (`screen_supplemental.py` →
`results/discovery_supplemental.json`; Phase 1 results are not rerun). It
cannot eliminate a candidate.

**Pronunciation identity** is tested before any consolidation
(`pronunciation_identity.py` → `results/pronunciation_identity.json`):
- matched-seed pairs, DTW-aligned MFCC distance;
- compared with take-to-take variation;
- one-sided Wilcoxon test.

The two pronunciations are kept separate unless proven identical. They are
not identical: the phoneme inputs differ.

**Extra held-out confusion set** (`lab_common.EXTRA_CONFUSION`):
- Words: Sylvia, Olivia, Siri, Syria, severe, trivia, "see via", Siva, Shiva,
  Civia, Vivian, "hey Sylvia", "hey Olivia".
- Clips: the same 24 speakers.
- Used for **evaluation only**, so the shared training negatives stay identical.
- **Every** model (original 15 and all supplemental) is scored on it, in the
  additive file `lab_eval_supp_cross.json`. The recommendation's false-wake
  factor uses the combined confusion rate for every model alike.
- Civia is the same sound as Sivia (SIV-ee-uh), so it is expected to trigger
  that model by definition.

## Limits (apply to every number here)

- All speech is synthetic, with no real elderly voices. Accents are limited
  to the voices available.
- Nothing passed through the Voice PE microphones or its XMOS front end.
- The TV audio is a read-speech proxy, not broadcast audio.
- Resident conditions (older, raspy, dentures, weak onset, shortened ending)
  are signal-processing simulations.
- The room is a simulated shoebox.
- All models are research-only (`LICENSES.md`).
