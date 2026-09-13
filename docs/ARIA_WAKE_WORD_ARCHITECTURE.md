# Aria Wake-Word — Smallest Viable Architecture

**Status: documented plan, no live prototype yet.** Written for Terminal 10
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

## The smallest viable architecture

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

## Engine choice — not yet decided, needs a real trade-off pass

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

## Why this is not implemented yet in this pass

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
