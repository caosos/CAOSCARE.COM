# Experiment (not adopted): local Whisper second-stage wake verification

**Status: preserved experiment, NOT the production fix.** Michael directed
(2026-09-24) that the underlying problem — the single-word "Aria" wake phrase
colliding with "area" — is solved by wake-phrase selection
(`docs/WAKE_PHRASE_LAB.md`), not by this verifier.

## What it did
When the sherpa-onnx keyword spotter fired, the listener collected ~0.4 s
more audio, re-heard the last ~2.4 s with a local Whisper base.en model
(sherpa-onnx, int8, on-device) and emitted a wake only if the text contained
the name. Failed closed if the model could not load. Heard text logged only
with `ARIA_WAKE_LOG_VERIFY_TEXT=1`.

## Evidence (synthetic, 2026-09-24)
| | real "Aria" wakes | false wakes |
|---|---|---|
| spotter alone (threshold 0.15) | 22/30 | 7/144 |
| spotter + Whisper tiny.en | 9/30 | 0/144 |
| spotter + Whisper base.en (name spelled aria/ariah/arya) | 17/30 | 0/144 |

Live listener process on a virtual audio device with the real false-trigger
phrases: 0 of 7 woke; 1 of 3 real "Aria" clips woke. Added ~0.6-0.8 s latency.
Whisper often transcribes "Aria" as "area", which is the collision itself.

## Where it is
`2026-09-24-whisper-wake-verifier.patch` (this folder) applies cleanly to
`room-node/aria_wake/` at commit `12dadd4`: `git apply
docs/experiments/2026-09-24-whisper-wake-verifier.patch`. It needs the
Whisper base.en model under `room-node/aria_wake/model/whisper-base.en/`
(setup in the patched README). The Room 214 listener remains OFF.
