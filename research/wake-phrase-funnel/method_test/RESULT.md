# Training-method A/B — result (2026-10-04): FAIL → stopped

**Product wake phrase remains HEY ARIA.** Okay Sequoia was only the test subject. Research only —
NOT COMMERCIALLY RELEASABLE; nothing flashed or deployed. Plan fixed in advance:
`PLAN_RECEIPT.md`. Numbers: `firmware/voice-pe-aria/lab/results/method_test/method_test_summary.json`.

## Before vs after (each at its matched threshold)

| Measure | Control (batch-1 Okay Sequoia) | Experiment (+ hard negatives) | Target |
|---|---|---|---|
| Threshold | 0.99 (max; limit not reached) | 0.99 (max; limit not reached) | — |
| Catch (all conditions) | 68.1% | 65.1% | ≥ 63% ✅ |
| Catch, TV on | 51.4% | 44.4% | ≥ 42% ✅ |
| Catch, simulated older voice | 28.5% | 24.3% | (reported) |
| Catch, low volume | 86.8% | 85.1% | (reported) |
| Wrong-word wakes | 0.10% | 0.03% | ≤ 0.5% ✅ |
| **Simulated false wakes/h** | **2.13** (12 in 5.6 h) | **1.07** (6 in 5.6 h) | **≤ 0.5 ❌** |
| …from the TV-dialogue stream | 4.29/h | 2.14/h | — |
| At fixed 0.90: catch / false wakes | 75.0% / 4.62/h | 71.8% / 2.49/h | — |

**Result: FAIL.** The hard negatives halved the false wakes and cut wrong-word wakes, at a cost of
3 points of catch and 7 points of TV-on catch, but false wakes stay at twice the limit even at the
strictest threshold. Per the stop rule, no other phrase or model was started.

## Training-data provenance (the only change)

- MLCommons People's Speech, config `clean`, validation shards 00000 and 00001, revision
  `f10597c5d3d3a63f8b6827701297c3afdf178272`; shard SHA-256 `b0e3dadd…5d21` and `2108fc6a…0e1a`
  (full values in `hardneg_manifest.json`). Licence: CC-BY / CC-BY-SA family (dataset card).
- 7,450 utterances, 13.7 h, resampled to 16 kHz; 0 excluded (no transcript contained "sequoia").
- Features built with the lab's identical seeded augmentation pipeline; added as one negative set
  at sampling weight 10, penalty 1, truncation `random` (same as the existing generic speech set).
- Everything else identical: the same 1,800 positive clips, shared negatives, recipe, 10,000 steps,
  seeds. Scripts: `fetch.py`, `prep.py`; recorded in the model's `training_parameters.yaml`.
- Model SHA-256: control `d2732b2e…b1d2`, experiment `64bc87af…4b15`.

## Evaluation-data proof

- Evaluation clips: 9,288 files, digest `01d530cf305c004699f4c227817e6e289d12c18b7a63b17df1b5b037d37b07a9`
  before and after — identical. Ambient streams: 6 files, digest
  `e56f94526cb2073681a342a67c6025bb061827a4612ede58622d1fdd83f32e0d` before and after — identical.
  (`results/method_test/eval_digest.json`)
- The experiment was scored on exactly the control's 26,784 clip-condition jobs, and the same
  ambient hours. Evaluation ran with the deterministic per-clip seed.
- The 26-model and batch-1 result files are unchanged.

## What this means

Hard negatives from a separate conversational/broadcast corpus move false wakes in the right
direction but not far enough on this phrase. Possible next steps — **Michael's decision; none
started**: a larger or more TV-like hard-negative set, a higher negative weight (a new pre-registered
test, not a retune of this one), or accepting that "okay"-led phrases are TV-dialogue prone. Hey
Aria and Hey Sivia are not run until the method is proven and Michael decides.
