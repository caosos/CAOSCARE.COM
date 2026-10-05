# Acoustic batch 1 — results (2026-10-04)

**RESEARCH ONLY — NOT COMMERCIALLY RELEASABLE.** Synthetic evidence; nothing flashed. Aria remains
the assistant identity. Numbers: `firmware/voice-pe-aria/lab/results/batch1/` (`batch_summary.json`,
`phase2_results.json`, `phase2_summary.csv`, `phase2_confusion.csv`, `phase2_cross_trigger.csv`,
`phase2_roc.csv`), produced by `report_batch.py` with the lab's own aggregation.

## Run

All 8 phrases were generated, trained, evaluated and cross-checked (15:06–19:10 CDT): 0 retries,
0 failures, no model dropped. Same method as the corrected 26-model lab (`772e216`, deterministic
evaluation). The 26-model results were not rewritten (the report regenerates byte-identical).

## Decision: no phrase passed the pre-registered rule → recommend a second batch (not started)

Rule (fixed before results): at the matched cutoff, simulated ambient ≤ 0.5 false wakes/h, catch
≥ 63%, TV-on catch ≥ 42%, wrong-word wakes ≤ 0.5%. **0 of 8 passed.**

| Phrase | Lab score | Catch (all) | TV on | Low volume | Older voice (sim.) | Wrong-word | Sim. false wakes/h | Cutoff | Fails |
|---|---|---|---|---|---|---|---|---|---|
| okay verona | 7.17 | 44.4% | 17.4% | 63.2% | 20.1% | 0.16% | 0.18 | 0.85 | catch, TV |
| hey nevina | 7.04 | 50.6% | 15.3% | 75.0% | 17.4% | 0.37% | 0.36 | 0.95 | catch, TV |
| okay sequoia | 5.10 | 68.1% | 51.4% | 86.8% | 28.5% | 0.10% | **2.13** | 0.99 (max) | ambient |
| okay juniper | 4.85 | 59.5% | 22.9% | 86.5% | 4.2% | 0.35% | **4.44** | 0.99 (max) | ambient, catch, TV |
| hey thomasina | 4.55 | 52.2% | 36.1% | 68.1% | 16.0% | 0.07% | **1.60** | 0.99 (max) | ambient, catch, TV |
| hey care companion | 4.07 | 45.7% | 14.6% | 70.5% | 4.9% | 0.12% | **1.78** | 0.99 (max) | ambient, catch, TV |
| hello home helper | 3.77 | 40.9% | 23.6% | 53.1% | 10.4% | 0.02% | **0.53** | 0.99 (max) | ambient, catch, TV |
| okay evergreen | 3.74 | 36.1% | 9.0% | 52.1% | 0.7% | 0.07% | **0.89** | 0.99 (max) | ambient, catch, TV |

Benchmarks (unchanged evidence): hey kookaburra 75.0% / TV 50.7% / older 43.1% / 0.16%; hey
callista 58.0% / 42.4% / 20.8% / 0.22%; okay velora 54.8% / 26.4% / 22.9% / 0.49%; hey aria
44.5% / 13.9% / 6.9% / 1.63% — all four within the ambient limit.

Scoring note: lab weights; batch text inputs from the funnel; natural identity real name 7,
invented 4, role phrase 7 (a reported addition — role phrases keep Aria as the name).

## What batch 1 showed

1. **The text funnel's TV-safety prediction did not hold.** All 8 had near-perfect text TV safety
   (8.6–10), yet 6 of 8 could not reach the simulated ambient limit even at the strictest cutoff,
   and every one of those failures came from the TV-dialogue stream (music adds 1/h for juniper
   and home helper; HVAC, room background and silence gave none). Text collision screening is not
   a substitute for acoustic false-wake testing.
2. **Okay Sequoia is the acoustic surprise:** best catch in the batch (68%, TV 51%, low volume
   87%, all three pronunciation forms 81–94%) and very low wrong-word wakes (0.10%) — but 2.1
   simulated false wakes/h from TV dialogue at the strictest cutoff. It is the only new phrase
   whose catch profile matches Hey Kookaburra.
3. **The two that stay quiet don't catch enough:** Okay Verona and Hey Nevina reach the ambient
   limit but catch only 44–51% (TV 15–17%) — no better than the existing finalists.
4. **Role phrases did not help:** Hello Home Helper and Hey Care Companion had the lowest
   wrong-word rates but weak catch and TV-dialogue false wakes; longer phrases did not buy catch.
5. **Simulated older voices are the weak spot for every model** (0.7–28.5%; Hey Kookaburra 43%).
   This simulation (−2 semitones, 0.9× tempo) is crude, but the gap is consistent.
6. Cross-triggers stayed low: the worst was Hey Thomasina waking on Hey Callista (18.8%) and Okay
   Verona / Hey Care Companion on Okay Lumaro (16.0% / 15.3%).

## Recommendation (Michael's decision — nothing started)

A second batch of at most 8 is informative only if it changes what failed here. Options:

- **A. Same method, different phrases:** pick phrases acoustically close to what worked (the
  Sequoia pattern: rare stressed vowel, K-W cluster, "okay" + 3 syllables) and to the quiet
  Verona/Nevina pattern. Risk: the text screen cannot predict the TV-dialogue failures.
- **B. Explicit, separately reported method change:** add TV-dialogue-style hard negatives to
  training (from a source kept separate from the evaluation stream), then retrain Okay Sequoia
  and the best 2–3 from batch 1 and compare against their batch-1 versions. This tests whether
  the failure is the phrase or the training data.
- Either way, no phrase from batch 1 is recommended for physical testing yet; the existing three
  finalists (hey kookaburra, hey callista, okay velora) remain the physical-test set.
