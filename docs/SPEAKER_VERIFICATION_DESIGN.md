# Resident Speaker Verification — design note (NOT IMPLEMENTED)

Status: **EXPERIMENTAL / design only** (2026-09-24). Nothing here is built,
installed, or connected to Room 214. Do not implement until Michael approves.

## 0. Ratified boundaries (Michael, 2026-09-24)

- **Speaker verification ≠ authentication.** It is optional *routing /
  confidence evidence* for the resident endpoint, never an access-control gate.
- **The wake phrase comes first.** A phrase that collides with ordinary
  speech ("Aria" / "area") is not rescued by speaker verification. The Wake
  Phrase Lab collision veto stands on its own (`docs/WAKE_PHRASE_LAB.md`).
- **No "resident only" gating yet.** Hard 1:1 gating would stop family, CNAs,
  staff and visitors waking Aria in the room. That policy is unresolved (§9).
- **Independent of** Aria identity, wake-phrase choice, the speech-to-speech
  model, Home Assistant, the pendant/emergency path, and the canonical
  operational service layer. It supplies evidence; it decides nothing alone.
- No custom speaker-model training. No automatic adaptive enrolment.

## 1. Candidates (research snapshot — re-verify at implementation time)

| | SpeechBrain `spkrec-ecapa-voxceleb` | WeSpeaker (ResNet34-LM, CAM++, ECAPA…) | pyannote `wespeaker-voxceleb-resnet34-LM` | sherpa-onnx speaker-embedding runtime |
|---|---|---|---|---|
| What | ECAPA-TDNN, cosine scoring; VoxCeleb1+2; EER 0.80 % VoxCeleb1-O (model card) | toolkit + many pretrained models, ONNX exports for most VoxCeleb models | pyannote wrapper of the WeSpeaker ResNet34-LM model | runtime (already used by `room-node/aria_wake`) that loads NeMo / WeSpeaker / 3D-Speaker ONNX embedding models |
| Library licence | Apache-2.0 | Apache-2.0 | pyannote.audio MIT | Apache-2.0 |
| Model licence | Apache-2.0 (model card) | follows dataset: VoxCeleb models **CC-BY-4.0** (commercial use allowed with attribution) | CC-BY-4.0 | per model (inherits the source model's licence) |
| Runtime | PyTorch (heavy on EliteDesk, poor on Android) | ONNX → onnxruntime / sherpa-onnx | PyTorch + pyannote stack | onnxruntime, C++, Python, **Android APKs published** |
| Maintenance | stable, older release (2021 model) | active (2026 commits) | active | active; we already pin 1.13.8 |

Embedding sizes, CPU cost and minimum useful duration are **not asserted
here**; commonly reported values (e.g. 192-dim for ECAPA, 256 for ResNet34)
must be read from each model's own files and measured on the EliteDesk.

**Evidence gaps for every candidate:** no far-field eMeet evidence, no
elderly-voice evidence, VoxCeleb is celebrity interview speech. All
thresholds must come from our own Room 214 measurements (§6).

## 2. Recommended first model (to benchmark, not to adopt blind)

**A WeSpeaker VoxCeleb ONNX model (ResNet34-LM first, CAM++ as the
comparison) run through sherpa-onnx.**

- same runtime already on the room node: one dependency, not a PyTorch stack;
- Apache-2.0 code, CC-BY-4.0 model (attribution only);
- ONNX + published Android builds → the same model can move to the
  phone + dock endpoint if that is ratified;
- SpeechBrain ECAPA is the reference comparison in the benchmark only.

Choice is confirmed or overturned by the Room 214 benchmark, not by popularity.

## 3. Enrolment model (multi-sample)

A resident profile is a **set of trusted embeddings, never one recording**:
near / far, quiet / loud, seated / lying down, morning / evening, tired or
hoarse when it naturally occurs, TV off / on. Each sample stores provenance:
`who enrolled, when, device, distance/condition label, duration, quality
score, embedding model + version, consent reference`. Conditions are
robustness labels only — never interpreted medically.

Scoring against a set: report max and mean-of-top-k cosine to the trusted
set; the right aggregate is chosen from benchmark data.

## 4. Adaptive profile (designed, NOT enabled)

- New audio never becomes training data automatically. It may become a
  **candidate** sample only if: staff/resident-confirmed session, high
  verification score, good quality score, no overlapping speech, no TV
  audio detected, not during Aria playback.
- Promotion candidate → trusted requires a human confirmation step and is
  logged with the reason. Poisoning defence: cap adaptive samples' share of
  the profile; never promote from false-wake sessions; keep enrolment
  anchors that adaptive samples cannot displace; drift check against anchors.

## 5. Real-time architecture and confidence fusion

```
room audio (local) → VAD → wake-phrase candidate (A)
                         ↘ speaker embedding over the wake utterance (B)
                         ↘ audio-quality / usable-speech estimate (C)
fusion → activate Aria? → during the conversation, keep adding embeddings (B)
```

- Evidence is kept **separate**: wake score (A), speaker similarity (B, raw
  cosine and — only if calibrated on our data — a calibrated score), quality
  (C), later context (D). No fake percentage: raw cosine is stored as cosine.
- Fusion is a small explicit decision table, e.g. strong A + any B → wake;
  borderline A + strong resident B → wake; borderline A + low B → no wake,
  log. B can never rescue a phrase the Wake Phrase Lab rejected.
- Incremental verification during a live session is plausible (embed each
  VAD segment, update running evidence), but window length and overlap must
  come from the chosen model's measured minimum-duration curve — not invented.
- Audio for verification never leaves the room node.

## 6. Room 214 benchmark (Michael as the test resident first)

Positives: near/medium/far, quiet/loud, seated/lying, TV off/on, room noise.
Negatives: another person, TV dialogue, Aria's own speaker output, recorded
Michael playback, synthetic voice, overlapping speech.
Measure: FAR, FRR, score distributions per condition, latency, minimum usable
speech duration, CPU, RAM. Report per distance/noise condition.

## 7. Spoof / replay

Ordinary speaker verification does **not** resist replay: a recording of the
resident will usually match. Recorded-Michael playback is in the benchmark to
*measure* that, not to claim protection. No anti-spoof/liveness claim is made
unless a separate countermeasure is implemented and tested.

## 8. Privacy / data handling

Voice embeddings are biometric-like resident data:
local storage only by default, encrypted at rest, access-controlled and
audited; raw enrolment audio minimised and deletable after embedding (retention
configurable); deletion and re-enrolment supported; provenance for every
sample; **no resident voice data or embeddings in the repository** (same rule
as private facility names). No legal/compliance claim beyond this.

## 9. Unresolved policy question (Michael to decide)

How should resident, staff, family, visitors and other permitted speakers
interact with voice verification? Options include: resident-only evidence
(others fall back to the wake phrase alone), a per-room list of enrolled
permitted speakers, or verification used only to label *who* spoke for
context — never to refuse. Pendant/emergency paths are never affected.

## 10. Smallest implementation sequence (after approval)

1. Offline benchmark tool (in `tools/`, isolated from runtime) that embeds
   recorded Room 214 test clips with 2 candidate models and prints score
   distributions — no live audio.
2. Decide model + aggregate + thresholds from that data.
3. Shadow mode on the room node: compute and log B next to wake events,
   affect nothing.
4. Only then consider fusion, and only with the §9 policy decided.

## 11. Unknowns that need physical testing

eMeet far-field embedding quality; lying-down / soft-voice FRR; TV and
Aria-playback false accepts; minimum usable duration of a short wake phrase;
EliteDesk CPU with wake KWS + embedding concurrently; replay susceptibility.

Sources: SpeechBrain model card (huggingface.co/speechbrain/spkrec-ecapa-voxceleb);
WeSpeaker repo and docs/pretrained.md (github.com/wenet-e2e/wespeaker);
pyannote/wespeaker-voxceleb-resnet34-LM model card; sherpa-onnx speaker
identification docs and APK list (k2-fsa.github.io/sherpa/onnx/speaker-identification/apk.html).
