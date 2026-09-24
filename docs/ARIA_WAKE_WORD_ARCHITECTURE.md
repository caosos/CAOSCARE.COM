# Aria Wake-Word — Smallest Viable Architecture

> **Update 2026-09-24 — single-word "Aria" is NOT accepted as the production
> wake phrase.** After the close-range proof below, the listener woke Aria five
> times overnight from background speech (02:06–02:46 UTC). The intended
> pronunciation "air-ee-uh" (`EH1 R IY0 AH0`) is phonetically **identical** to
> the common word *area*. **The listener is OFF.** Aria remains the assistant's
> name; the wake phrase will be chosen by the Wake Phrase Lab
> (`docs/WAKE_PHRASE_LAB.md`, `tools/wakelab/`). No replacement has been
> selected. A local Whisper verifier experiment is preserved, not adopted
> (`docs/experiments/2026-09-24-whisper-wake-verifier.md`). The listener/page
> architecture below remains valid for whichever phrase is chosen.

**Status (2026-09-23): IMPLEMENTED and PHYSICALLY VERIFIED at close range in
the Room 214 test environment** (EliteDesk + eMeet). Code lives on branch
`aria/wake-word-proof` (commits `12dadd4`, `ab2ef40`) — **not yet merged to
`main`**, pending Michael's merge approval. Far-field capture is the open
constraint (see "Current limitations"). The 2026-09-10 plan below is
preserved as history; where the build proved part of it wrong, that is
marked in place rather than deleted.

## Current state (2026-09-23)

| Layer | Status |
|---|---|
| Natural voice activation (say "Aria", no tap/pendant) | **Ratified requirement** (Michael, Terminal 5 2026-08-02; Terminal 10; Aria Live directive 2026-09-22) |
| Local, on-device detection — no continuous room audio to any cloud | **Ratified requirement** |
| sherpa-onnx keyword spotter + room-page trigger | **Implemented** (branch above) — engine choice is **experimental / under evaluation** |
| Wake → existing Realtime conversation → real HA light → verified → rest → wake again | **Physically verified**, close range, Room 214, 2026-09-23 |
| Far-field (bed distance, TV on) reliability | **Not proven** — active work |
| False-wake rate over meaningful room-hours | **Not measured** — do not claim one |
| Android phone endpoint running the same protocol | **Planned / under evaluation only** (see Product Baseline §2) |

### Wake word and pronunciation

Target wake word: **Aria**, spoken **"air-ee-uh"** — three syllables. This is
the same three-syllable requirement recorded since 2026-08-02
(`commands/TERMINAL_5_ARIA_VOICE_FIRST.md`, "Ar-i-a"). **Do not substitute
the two-syllable "Arya" / "ar-yuh" form**, in a keyword list, model training
set, or prompt. The current keyword file contains only the `ARIA` spelling
(`room-node/aria_wake/keywords.txt`); no "ARYA" variant is enabled.

### What was built (and why this shape)

```
eMeet (PulseAudio default source; shared, non-exclusive tap)
   │
   ▼
room-node/aria_wake/aria_wake.py      on-device keyword spotter (sherpa-onnx KWS)
   │  ws://127.0.0.1:8765  (localhost only; page-origin allowlist)
   ▼
room page /kiosk/<id>?wake=1          lib/useWakeWord.js + lib/wakeWordClient.js
   │  starts the EXISTING no-event conversation path, trigger_source "wake_word"
   ▼
existing POST /realtime/session → lease claim → Realtime mint (unchanged)
   │
   ▼
existing tools → /devices/... → device_adapters.execute_home_assistant
   → HA service call → HA state read-back → verified or HTTP 502
   → Aria confirms only a verified result
```

- **Listener modes:** `listening` → wake → `pending` → page reports
  `conversation` (detections suppressed, so Aria's own voice cannot re-trigger)
  → session ends → page reports `listening` → 1.5 s cooldown → `listening`.
  An unconfirmed wake expires back to `listening` after 20 s.
- **Room page:** wake word is opt-in per endpoint (`?wake=1`). A wake opens
  **no resident event (Alert)** — it uses the same no-event path as a
  conversation-only session; the pendant retry gate is not touched by wake
  sessions. The pendant safety system is separate and unchanged.
- **Observability:** `activation_events` layer `wake_word`:
  `wake_listener_connected/disconnected`, `wake_word_detected` (wake_id,
  audio device, detector, threshold), `wake_word_ignored`,
  `wake_word_session_bound` (wake_id → session_id, via the room lease's
  `trigger_source`), `wake_listening_resumed`. Listener JSON log on stdout.
  Session end reasons come from the existing `realtime_diagnostics`.
- **Protocol is the portable part.** The Python listener is endpoint-specific;
  an Android endpoint would run a native detector in a foreground service and
  speak the same WebSocket protocol (`room-node/aria_wake/README.md`).

### Decisions and alternatives (2026-09-23)

| Question | Chosen | Alternatives considered | Why |
|---|---|---|---|
| Detector engine | sherpa-onnx open-vocabulary KWS, `gigaspeech-3.3M` int8 (Apache-2.0) | openWakeWord (Michael's stated primary candidate); Picovoice Porcupine | No usable pretrained openWakeWord "Aria" model exists — the only community "Aria" model (openwakeword.com library, id 3486) is es_ES-trained with published recall 0.01. A custom openWakeWord model needs a training run (hours on this CPU-only host). Porcupine is proprietary with a vendor account/licence. sherpa-onnx needs no training and ships an Android build. **This is a proof engine, not a final choice.** |
| How the page learns "Aria" was heard | localhost WebSocket from listener to page | Plan's `POST /realtime/room/{room}/activate` | **Plan was wrong here** — see correction below. |
| Resident event on wake | none (conversation-only path) | mirror "I just want to talk" (which creates a `comfort` Alert) | A wake word is not a request for help; creating staff-visible events per "Aria" would change staff workflow. |
| Gate for enabling | page URL `?wake=1` | build-time env var | No dev-server restart; per-endpoint; production pages never try to connect. |

**Correction to the 2026-09-10 plan:** the plan said the listener should call
`POST /api/realtime/room/{room}/activate` and that this "needs zero changes."
Inspection during the build showed `/activate` only **claims the room lease**;
nothing notifies the room page, and a lease claimed by the listener under its
own session id would make the page's own `POST /realtime/session` mint be
refused as `already_active`. The trigger therefore goes to the page, and the
page's normal mint claims the lease. No backend activation endpoint changed.

### Physical verification (Room 214, 2026-09-23/24 UTC)

Runtime: :3000 → :8092 both serving `aria/wake-word-proof` (backend restarted
on `12dadd4`); listener on the eMeet
(`alsa_input.usb-EMEET_EMEET_OfficeCore_Luna_Plus_…mono-fallback`).

- Four voice-started sessions with no screen or pendant touch; wake → session
  bound in < 1 s (`activation_events`, sessions `rt_51j542hf…`,
  `rt_3tste185…`, `rt_wpngzbuw…`, `rt_vurxsdwz…`).
- Overhead light OFF and ON through the existing path, each
  `device_commands.verified = True` from Home Assistant read-back before Aria
  confirmed (`dev_facc6dbc7e13` → `light.smart_multicolor_bulb_2`).
- "Goodbye"-style endings closed the session; the page reported idle and the
  listener logged return-to-listening every time; the next "Aria" worked.
- "Aria" said during an open conversation was suppressed (logged
  `detection_suppressed`), as designed.
- Michael's field report: reliable at close range, practical ~3–4 ft; from
  the bed he had to speak louder.
- Defect found and fixed in the same session: a **refused** `mark_resting`
  ("I'm going to bed" → guard asks "would you like me to go quiet?") silenced
  Aria without speaking the question (`rt_wpngzbuw_1790215179553`). Fixed in
  `ab2ef40` — refusals are now spoken.

Synthetic pre-test (OpenAI TTS voices, not real speakers — indicative only):
continuous noisy stream through the listener's own code detected 24–27/30
"Aria" utterances with 0–1 false detections across 48 non-wake sentences.
One streaming drift defect found and fixed before the room test (silence-based
stream reset).

### Current limitations (open)

- **Far-field capture is the current constraint, not a proven model failure.**
  Note the two paths differ: the Realtime conversation hears Chrome's
  processed capture (echo cancel / noise suppression / auto-gain), and eMeet
  conversations have been reported working at 10–12 ft
  (`docs/ROOM_AUDIO_ARCHITECTURE.md`); the wake listener reads the raw
  PulseAudio source with no gain stage. Whether bed-distance misses are mic
  reach, input level, or detector threshold is **unmeasured**.
- **False-wake rate unmeasured.** Required empirical programme before any
  claim: log every detection (already logged) in a quiet room, normal
  conversation, TV/audio playing, and at several distances, and report false
  activations per room-hour over meaningful hours. The engine exposes no
  confidence score (logged as `null`).
- Listener and backend run under `nohup` — they do not survive a reboot.
- The room page must stay open in Chrome; Chrome autoplay after a no-touch
  start worked in this test but has not been proven after a cold browser
  launch.
- Still-open adjacent debt: browser tools call unauthenticated
  `/devices/public/...`; Aria once said "I'll be quiet now" in the same
  response as a `mark_resting` call that was then refused (speech before tool
  result).

### Next steps (in order)

1. Merge the branch to `main` (Michael's approval).
2. Boot-persistent services for the listener and a Chrome kiosk launch.
3. Far-field measurement: detections vs distance/level with and without a
   gain stage or threshold change — change one variable at a time, keep the
   working configuration as the baseline.
4. False-wake soak (quiet / conversation / TV) with per-room-hour results.
5. Decide engine: keep sherpa-onnx, or train a custom openWakeWord "Aria"
   (air-ee-uh) model and compare on the same recordings.

---

## Original plan (2026-09-10) — preserved as history

**Status at the time: documented plan, no live prototype yet.** Written for Terminal 10
(`commands/TERMINAL_10_CONVERSATION_PARITY.md`, item 4: "First document the
smallest viable architecture and dependencies. Then implement only if it can
be done without destabilizing the proven Realtime/device-control path.")

This is not a redesign. It is the smallest addition that lets a resident say
"Aria" (three syllables, Ar-i-a) and have the existing, proven Realtime
session start — nothing about the Realtime/device-control pipeline itself
changes.

## What already exists (verified, not assumed)

- `docs/ARIA_VOICE_FIRST.md` (2026-08-02 Phase A): no wake-word / Wyoming /
  openWakeWord / Piper / local-STT stack exists anywhere in this repo or on
  the EliteDesk host today. This is genuinely net-new work, not a
  misconfigured existing piece.
- `docs/ROOM_AUDIO_ARCHITECTURE.md` (decided, 2026-08-27): the room has
  exactly **one** audio capture/playback endpoint per room — the eMeet
  Luna Plus (or equivalent conferencing speakerphone) sitting near the
  resident. Capture-at-resident is the architecture; a second microphone
  (e.g. one dedicated to wake-word) is explicitly the rejected pattern this
  doc warns against. A wake-word listener must tap the SAME capture stream
  Aria's Realtime session already uses, not a new mic.
- `docs/ARIA_VOICE_FIRST.md` also mechanically verified this host's audio
  path: the eMeet is the OS default PulseAudio sink and source, and both
  `arecord`/`speaker-test` work end to end. A wake-word listener has a
  proven capture point to attach to.
- **`models.py:1552`** — `Alert.trigger_source: str = "unknown"` already
  documents `pendant | wake_word | handset | screen_talk | manual_kiosk` as
  its anticipated values, and `claim_or_reuse_room_lease()` /
  `POST /api/realtime/room/{room}/activate`
  (`backend/routes/realtime_room_lease.py`) accept `trigger_source` as a
  **plain string**, not a fixed enum. **This means the activation contract
  a wake-word detector needs already exists and needs zero Level 1 schema
  or endpoint changes** — see "Level 1 dependency" below.
- `docs/CURRENT_NODE_STATUS.md` (2026-08-21 era): wake word was "confirmed
  lowest priority per Michael's own directive" at that time. Terminal 10
  (2026-09-09/10) explicitly re-elevates it as one of four required
  conversation-parity work items. This document treats Terminal 10 as the
  current, superseding priority.

## The smallest viable architecture (2026-09-10 plan — the `/activate` step below was proven unworkable; see "Correction" above)

```
eMeet mic (existing capture endpoint, already the default PulseAudio source)
        │
        ▼
local wake-word listener process on the EliteDesk
  (new, small, always-on; NOT part of the FastAPI backend or the browser)
        │  "Aria" detected
        ▼
POST /api/realtime/room/{room}/activate
  { trigger_source: "wake_word", room, kiosk_id }
  (existing endpoint - realtime_room_lease.py, unchanged)
        │
        ▼
existing Level 1 activation fencing + lease claim
  (resident_session_binding.py / realtime_room_lease.py - unchanged)
        │
        ▼
existing, proven Realtime session mint
  (realtime_resident_session.py::_mint - unchanged by this work)
```

The listener is a **trigger**, not a conversation participant. It does one
thing: recognize "Aria" in the live audio stream and call an endpoint that
already exists. It has no knowledge of residents, rooms beyond its own
config, tools, or the Realtime protocol.

## Level 1 dependency — verified, not a blocker

Terminal 10's instruction is to document any Level 1 interface/change
requirement instead of duplicating that lane's work. Having inspected it:

**No Level 1 change is required.** `trigger_source` is already a free-form
string on the exact activation path a wake-word detector needs
(`POST /realtime/room/{room}/activate`), and `"wake_word"` is already named
in the model's own comment as an anticipated value. A wake-word prototype is
purely additive - it becomes a fourth caller of an endpoint three trigger
sources (`pendant`, `manual_kiosk`, `unknown`) already use, with no request/
response shape change. If this changes (e.g. Level 1 later tightens
`trigger_source` to a strict enum), that enum must include `"wake_word"` -
flag it to the Level 1 lane at that time, do not silently work around it.

## Engine choice — as assessed 2026-09-10 (superseded 2026-09-23: sherpa-onnx chosen for the proof; see "Decisions and alternatives")

Two realistic options, neither installed or evaluated hands-on yet:

1. **openWakeWord** (Apache-2.0, local, no cloud dependency). Ships generic
   pretrained models ("hey jarvis", "alexa", etc.) but **not** "Aria" - a
   stock generic model must not be substituted for the actual wake word
   (this has been a standing requirement on this project). Using it for
   "Aria" requires training a custom model, which needs a set of real or
   synthesized "Aria" utterances (their training pipeline supports
   TTS-augmented synthetic data, so live recordings of Michael/residents
   are not strictly required, but improve accuracy). Fully local, fully
   free, but the custom-model training step is real work with an accuracy
   unknown until tried.
2. **Picovoice Porcupine** (custom wake-word via the Picovoice Console,
   free tier for personal/prototype use, commercial licensing needed
   before a paid multi-facility deployment). Faster to get a usable custom
   "Aria" model (their console generates one from typed text plus a small
   voice sample), typically lower false-accept rate out of the box, but
   introduces a vendor account/quota and a licensing question for
   production that must be decided before shipping to real facilities.

Neither should be chosen by guessing. The next concrete step is a short,
explicit hands-on comparison (a few hours, not a redesign): install both,
train/generate an "Aria" model with each, run them against the same short
recorded sample set (quiet room, TV on, resident-distance speech), and
record false-accept/false-reject counts before picking one.

## Why this was not implemented in the 2026-09-10 pass (historical)

Terminal 10 explicitly allows "a working bounded prototype OR a documented,
verified blocker." Building and testing a real always-listening audio
process against the actual eMeet hardware requires either physical access to
the EliteDesk with Michael present (to judge real detection quality in the
real room, not a synthetic test), or a specific engine choice made from the
hands-on comparison above - neither of which is something to force blind
from this session without risking exactly the kind of live-audio regression
`docs/reports/2026-08-23-1345-semantic-vad-failed-experiment.md` already
documents happening once on this same voice pipeline. This document is the
verified architecture + verified non-blocker (Level 1 side); the engine
trade-off pass and the physical listening test are the next safe steps,
not skipped work.

## What a bounded first prototype would look like, when undertaken

- A small standalone process (not inside `backend/` or the React app) that:
  1. opens the eMeet's existing PulseAudio monitor/source (read-only tap,
     never takes exclusive ownership of the device Aria's own session uses);
  2. runs the chosen wake-word engine on that stream;
  3. on a detected "Aria," calls
     `POST /api/realtime/room/{room}/activate` with
     `trigger_source: "wake_word"` and the room's known `kiosk_id`;
  4. does nothing else - no audio storage, no transcription, no direct
     OpenAI calls.
- Acceptance before calling it "working": a real, in-room test with Michael
  saying "Aria" produces exactly one activation and one Realtime session,
  a TV playing in the background does not cause spurious activations over a
  sustained period, and the existing pendant/kiosk-button trigger paths are
  demonstrably unaffected (same acceptance sequence Level 1 already uses).
