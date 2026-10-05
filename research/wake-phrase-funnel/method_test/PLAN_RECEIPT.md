# Training-method A/B — plan receipt (fixed before any result), 2026-10-04

**The product wake phrase remains HEY ARIA. Okay Sequoia is only the controlled test subject; it is
not a product candidate.** Research only — RESEARCH ONLY / NOT COMMERCIALLY RELEASABLE. Nothing
flashed or deployed.

## Question

Does adding TV-dialogue-style hard negatives to training fix batch 1's false-wake problem without
losing catch? Okay Sequoia was chosen because its failure in batch 1 was false wakes, not catch.

## Control (existing, not retrained)

Batch-1 Okay Sequoia (`runs/lab/okay_sequoia`), results in
`firmware/voice-pe-aria/lab/results/batch1/`:

| Measure | Control |
|---|---|
| Matched cutoff | 0.99 (max; limit not reached) |
| Catch (all) | 68.1% |
| Catch, TV on | 51.4% |
| Catch, older voice (sim.) | 28.5% |
| Wrong-word wakes | 0.10% |
| Sim. false wakes/h | 2.13 |

SHA-256: model `d2732b2e7c995e67e8fc74f52b907f21c1a3743329796e521c80b458d4f7b1d2`,
`lab_eval.json` `e57c47587da9c5cc92f6975db61f3bce28fae263f3688e1f8d84b7f33e9f8b5f`,
`lab_eval_supp_cross.json` `5e93e7095a976f2facfd29a59b9f967177920fee82634ea6741cb28c31410390`.

## Experiment (one model: `okay_sequoia_tvneg`)

Identical to the control except one added negative training set:

- **Source:** MLCommons People's Speech, config `clean`, **validation** shards 00000 and 00001,
  pinned revision `f10597c5d3d3a63f8b6827701297c3afdf178272`. Licence per the dataset card: CC-BY /
  CC-BY-SA family. People's Speech is transcribed public-domain-style broadcast/recorded speech
  (archive.org sources) — conversational/broadcast style, a completely different corpus from the
  evaluation TV-dialogue stream (LibriSpeech test-clean) and from every evaluation clip.
- **Selection rule (fixed):** every utterance in those two shards, except any whose transcript
  contains "sequoia" (so the positive word is never trained as a negative). No other filtering,
  no choice by content, no look at evaluation results.
- **Processing:** resampled to 16 kHz mono; features generated with the lab's identical seeded
  augmentation and spectrogram pipeline (`train_lab.features`, repeat 1).
- **Training weight (fixed):** sampling weight 10.0, penalty 1.0, truncation `random` — the same
  as the existing generic `speech` negative set. Nothing else changes: same 1,800 positive clips
  (`samples/lab/train/positives/okay_sequoia`), shared negatives, microWakeWord recipe, 10,000
  steps, seeds.

## Evaluation (byte-identical to batch 1)

Same evaluation job list as the control (own positives under 18 conditions; all 26 + batch-1
phrases as cross-trigger clips; held-out negatives, sentences, extra confusion list; the five
ambient streams), deterministic per-clip seed. Evaluation set digest before the experiment:

- evaluation clips: 9,288 files, `01d530cf305c004699f4c227817e6e289d12c18b7a63b17df1b5b037d37b07a9`
- ambient streams: 6 files, `e56f94526cb2073681a342a67c6025bb061827a4612ede58622d1fdd83f32e0d`

The digest is recomputed after the run and must match.

## Pass target (from the directive)

At the experiment's matched cutoff: simulated false wakes ≤ 0.5/h, catch ≥ 63%, TV-on catch
≥ 42%, wrong-word wakes ≤ 0.5%.

## Stop rule

- **Fail:** stop. No more phrases.
- **Pass:** stop and report. No further models (Hey Aria, Hey Sivia) start without Michael's
  decision.
- One run only; no retuning of the weight or data against the evaluation set.
