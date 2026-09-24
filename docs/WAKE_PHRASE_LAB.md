# Wake Phrase Lab — why, method, limits

**Status (2026-09-24): Step 1 built — text/phoneme stage only.** No
replacement wake phrase has been selected; selection requires the later
acoustic, adversarial, soak and physical Room 214 stages. Code:
`tools/wakelab/` (how to run: its README).

## Why it exists

**Aria remains the assistant's name and identity.** The single-word "Aria"
is **not accepted as the production wake phrase**: on 2026-09-24 between
02:06 and 02:46 UTC, the Room 214 listener woke Aria five times from
background speech (transcripts included "that area", "underneath her",
"thirteen", "Buna ziua"; sessions `rt_rfi71p83`, `rt_7c7mkf80`,
`rt_aj4lz20f`, `rt_r2b4te5e`, `rt_e7swwihd`). The lab then confirmed the
cause at the dictionary level: the intended pronunciation "air-ee-uh" is
`EH1 R IY0 AH0`, **identical** to the common word *area* (CMUdict). Tuning a
detector cannot separate two phrases that are the same sounds, so the wake
phrase itself must be chosen for low collision with ordinary speech.

A local Whisper second-stage verifier was tried the same night (rejected
7/7 false-trigger phrases in a synthetic test but also rejected many real
"Aria"s). It is **not** the production fix; it is preserved as an experiment
in `docs/experiments/2026-09-24-whisper-wake-verifier.md`.

## Method (Step 1)

1. **Corpus** (`config/sources.yaml`, provenance manifest per run):
   wordfreq top 100k words incl. subtitle/TV data (68k with CMUdict
   pronunciations); 2-3-word phrases counted from Tatoeba's 15.7M words of
   everyday sentences (748k phrase items); Census common first names and
   top-5000 surnames; FDA drug names (optional, G2P pronunciations);
   CAOSCare-authored lists (senior living, caregiving, medical, room/building,
   commands, greetings, reduced speech, **distress words**, Room 214
   regression phrases) and generated numbers/dates/times; optional private
   facility names (local only, redacted). Total 833,832 items.
2. **Phonetics**: ARPAbet (CMUdict), g2p_en for words CMUdict lacks, pinned
   overrides for a candidate's intended pronunciation (Aria = air-ee-uh).
   Multiple dictionary pronunciations are kept. Rule variants model casual
   speech and accents (Mary/marry/merry, cot/caught, pin/pen, vowel
   reduction, non-rhotic R, H-dropping) and clipped starts/ends.
3. **Confusability model** (`phonetics/features.py`): explicit phoneme
   substitution costs from place / manner / voicing and vowel height /
   backness / rounding / glide, anchored to classic perception findings
   (place most confusable in noise, voicing and nasality most robust).
   PanPhon's generic distances were tried first and rejected as implausible
   for this purpose (e.g. S/Z cost 0.03).
4. **Search**: rapidfuzz pre-filter by length pools, then weighted phoneme
   alignment — whole-item, candidate-inside-item (flagged when it straddles
   a word boundary), and item-inside-candidate.
5. **Separate metrics — never one score**: exact, near, inside words/phrases,
   across word boundaries, words hidden inside, facility/domain, names,
   distress, clipped, accent/casual variants, rough exposure (look-alike
   events per hour at ~150 words/min), speakability.
6. **Rejection gates** (all evaluated, all reported): G1 exact collision
   with common speech · G2 near collision with high-frequency speech · G3
   sound occurs inside common words / across word boundaries · G4
   facility vocabulary, commands, names (drug names reported, not gated by
   default) · G5 distress/safety words · G6 clipped start/end · G7 accent or
   casual variant · G8 speakability floor. Only matches that can make
   ordinary speech SOUND LIKE the candidate gate; a common word hidden
   inside a candidate is reported, not gated. Speakability never offsets a
   collision gate.
7. **Pronunciation policy**: a pinned intended pronunciation is
   authoritative and other dictionary pronunciations are information only
   (they cannot rescue a candidate); otherwise a candidate is rejected if any
   of its dictionary pronunciations fails.

Calibration evidence (2026-09-24): "aria" REJECT (G1: area), "okay nabu" and
"hey mycroft" PASS (text stage), "hello", "computer", "alexa", "jupiter"
REJECT on real collisions, "hey jarvis" REJECT only on the surname Jarvis.

## Limitations (keep in view)

- **Text/phoneme analysis predicts acoustic danger; it does not prove real
  acoustic performance.** Only acoustic, adversarial, soak and physical
  Room 214 testing can.
- Phrase frequencies come from Tatoeba (written everyday sentences), not
  recorded senior-living rooms or TV; subtitle data enters only as word
  frequency via wordfreq (a ~2021 snapshot). No licensable conversational
  corpus was found.
- 32% of the top-100k wordfreq words have no CMUdict entry and are skipped.
- G2P pronunciations (names, drugs, invented words) are guesses.
- The confusability model and all thresholds are engineering judgements,
  recorded in `config/default.yaml` and `phonetics/features.py`.
- English only. No older-adult or dysarthric speech data.
- Room 214 transcripts are what the conversation model heard after each
  wake, not proof of the audio that triggered the detector.
- Licensing: wordfreq data is CC-BY-SA 4.0 and Tatoeba CC-BY 2.0 FR; used
  locally, not redistributed. Commercial use of any derived artefact and of
  detector models needs review.

## Adding a corpus or language
Add a source to `config/sources.yaml` (url, license, attribution, pin
sha256 after first fetch), a reader in `corpus/build.py` returning items
with a `metric` class, and — for another language — a G2P/lexicon backend
producing the same phoneme tuples. Authored lists: add a YAML file under
`wakelab/corpus/domain/`.

## Path to physical testing (later steps)
generate → collision-filter (this stage) → speakability ranking (Pareto,
collision first) → adversarial hard negatives from each finalist's nearest
neighbours → synthetic acoustic testing (labelled SYNTHETIC) → soak testing
(false wakes per hour) → Room 214 physical acceptance sheet. A candidate
advances only by surviving each stage.
