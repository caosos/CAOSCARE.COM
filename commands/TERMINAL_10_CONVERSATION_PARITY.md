# TERMINAL 10 — CONVERSATION PARITY / PERSON-SPECIFIC ARIA

## Mission

Make Resident Aria reproduce the class of interaction Michael experiences in ChatGPT voice: not merely correct answers, but person-specific interpretation continuity, natural turn timing, appropriate response length, interruption behavior, pacing, and memory-backed understanding.

This is a bounded conversation-engine lane. Do not redesign unrelated CAOSCare architecture.

## Required first reads

Before changing code, read and follow:

1. `AGENTS.md`
2. `docs/PROJECT_STATE.md`
3. `docs/CAOS_CARE_AGENT_ONBOARDING_CONTRACT.md`
4. `docs/ARIA_VOICE_FIRST.md`
5. `docs/reports/2026-08-23-2152-voice-regression-matrix.md`
6. `docs/reports/2026-08-23-1345-semantic-vad-failed-experiment.md`
7. `backend/routes/realtime_audio_config.py`
8. `backend/routes/realtime_companion_prompt.py`
9. `frontend/src/lib/useRealtimeVoice.js`
10. `frontend/src/lib/realtimeSessionUpdate.js`

Inspect current branch and runtime state before writing. Preserve accepted device-control behavior and existing resident-assistance event behavior.

## Why this lane exists

The Realtime transport already works. Device tools already work. The remaining gap is that the runtime around the model is too generic.

Canonical interpretation example:

```text
Michael says: dos savor
Context: he is learning Spanish and commonly speaks phonetic/approximate Spanish
Desired interpretation: dos sabores
Meaning: two flavors
```

Aria must not treat imperfect input as isolated raw text when scoped prior context and learned person-specific patterns make the likely intent clear.

## Current verified constraints

- Realtime voice is WebRTC/OpenAI Realtime via `useRealtimeVoice.js`.
- Current turn detection is `server_vad`, threshold 0.5, 300 ms prefix padding, 1000 ms silence, `create_response: true`, `interrupt_response: true`.
- A prior `semantic_vad`/low-eagerness experiment caused a real ~38-second speech-detection dead zone and was reverted. Do not repeat it blindly.
- Resident prompt already contains pacing/personality instructions.
- Resident profile/memory is already injected into the prompt.
- `realtimeSessionUpdate.js` currently hard-codes transcription language to `en`, which conflicts with natural bilingual/Spanglish use and must be evaluated.
- Wake word `Aria` is still not implemented in the runtime.

## Required work

### 1. Multilingual transcription audit and fix

Inspect the current OpenAI Realtime transcription configuration and current API behavior.

Goal: do not force English when the resident naturally mixes English and Spanish or switches languages.

Requirements:
- verify the current supported Realtime transcription options against authoritative OpenAI API behavior before changing fields;
- remove or replace the hard-coded `language: "en"` only if the current API supports a better multilingual path;
- preserve English performance for normal resident speech;
- add regression coverage for English, Spanish, and mixed-language turns where feasible.

Do not guess unsupported API fields.

### 2. Person-specific interpretation layer

Design and implement a scoped mechanism for durable, person-specific language/interpretation patterns.

It must be able to represent examples such as:
- phonetic approximations;
- recurring word substitutions;
- personal shorthand;
- preferred wording;
- language-learning patterns;
- context-dependent meanings confirmed repeatedly by the person.

Requirements:
- resident-scoped; no cross-resident leakage;
- retrieval must happen before or during prompt/context construction so the model can use the pattern on the relevant turn;
- corrections/confirmations must be able to strengthen or update a pattern without silently overwriting unrelated memory;
- preserve the user's original wording when teaching/correction is useful;
- uncertainty must remain explicit when multiple interpretations are plausible;
- do not build a giant generic memory dump into every turn.

Canonical acceptance test:

```text
Given relevant Michael-style Spanish-learning context and a learned phonetic pattern,
"dos savor" should be interpreted as "dos sabores" / "two flavors".
```

For a teaching surface, preserve this sequence when appropriate:

```text
what the person said
→ what Aria understood
→ corrected/natural form
→ meaning in the person's primary language
```

### 3. Conversation parity instrumentation

Add enough diagnostics to measure the feel of the interaction rather than tuning blindly.

At minimum capture or derive per session/turn where feasible:
- user speech start/stop;
- response start;
- silence gap before Aria responds;
- whether Aria was already speaking when the user began;
- interruption/barge-in events;
- transcript/correction events;
- response length or duration;
- user-requested correction / misinterpretation marker where available.

Do not store raw audio merely for this lane.

### 4. Wake-word implementation plan, then bounded prototype

Inspect the existing wake-word directives and current EliteDesk/Home Assistant architecture.

Preferred direction remains local wake-word detection for `Aria` (three syllables: Ar-i-a), with the CAOSCare Realtime session activated only after wake detection.

Do not stand up an unrelated second full conversational assistant stack if all that is needed is local wake detection feeding the existing CAOSCare Realtime path.

First document the smallest viable architecture and dependencies. Then implement only if it can be done without destabilizing the proven Realtime/device-control path.

## Acceptance philosophy

The target is not "sounds nicer." The target is observable parity improvements.

A successful pass should prove:
- bilingual/Spanglish input is not artificially forced through English-only transcription;
- at least one person-specific interpretation pattern survives across sessions and affects interpretation correctly;
- the original utterance can remain visible/auditable beside the interpretation;
- existing light/device tool calls still work;
- existing resident identity/memory isolation still works;
- turn-taking diagnostics make premature interruptions and long response gaps measurable;
- wake-word work has either a working bounded prototype or a documented, verified blocker.

## Do not do

- Do not call Helen/Michael identity mismatches a defect when Michael is intentionally testing inside Helen's resident account.
- Do not broadly retune VAD by intuition; preserve the prior regression evidence.
- Do not replace the existing Realtime pipeline with a new voice stack without evidence that it is necessary.
- Do not touch production deployment without Michael's explicit approval.
- Do not merge unrelated Admin/Operations, transportation, or other lane work into this change.

## Handoff

Before stopping:
- run focused tests plus relevant existing Realtime tests;
- report every production-code file materially modified and its line count;
- update `docs/PROJECT_STATE.md` with what changed, what was verified, blockers, and next safe step;
- commit on the appropriate conversation/parity branch only after the bounded work is coherent and tested;
- do not deploy production without Michael's explicit approval.
