# Room Audio Architecture — decision record

**Status: decided.** Recorded 2026-08-27 from Michael's field session report and
directive. This is the canonical architecture record for how audio capture,
Aria playback, and TV/media playback are meant to relate to each other in a
resident room. It supersedes informal discussion on the topic; prior research
reports (linked below) remain valid as the forensic history that led here,
not as competing sources of truth.

## The decision

- **EliteDesk** = room compute + TV display/source routing. It is the node
  that runs CAOSCare (backend + kiosk frontend) and drives what the TV shows;
  it is not itself a room audio device.
- **eMeet** (or whatever conferencing-speakerphone-class device occupies this
  role in a given room) sits near the resident and is the **single room audio
  capture/playback endpoint for Aria** — the one microphone and the one
  speaker Aria's voice pipeline uses in that room.
- **TV audio should eventually be brought into the CAOSCare audio path**
  electrically/digitally and played back through that same eMeet, so **one**
  acoustic echo cancellation (AEC) path owns both Aria's own playback and TV
  playback. Two independent audio-output paths in the same room is what
  defeats AEC — a device only cancels echo of audio it knows it's playing.
- **Do not solve TV noise with a second microphone.** Adding a TV-side mic is
  explicitly rejected as an approach — it multiplies the number of audio
  paths needing echo cancellation instead of reducing it to one.
- **TV internal speakers must be muted/off whenever CAOSCare owns TV audio**
  — once TV audio is routed through the eMeet, the TV's own built-in speakers
  become a second, uncontrolled playback path and must not also be live.
- **Handset remains the guaranteed-duplex fallback surface** — a corded/
  wireless handset held at the ear sidesteps room acoustics and AEC
  entirely (near-field, one direction in each ear/mouth), and stays the
  fallback path regardless of how the room-speaker setup evolves.
- **Capture-at-resident is the architecture; capture-at-TV is not.** The
  microphone lives where the resident is, not at or near the television.

## Why (the acoustic reasoning)

An AEC engine cancels echo by comparing what a device is capturing against
what that *same* device (or a path it's aware of) is currently playing. A
room with two independent, uncoordinated playback sources — Aria's voice
through the eMeet, and a TV playing through its own internal speakers, or a
soundbar not fed by the same box — gives any single-endpoint AEC nothing to
cancel the *second* source against. Multiple prior sessions found exactly
this failure mode in practice (see the research reports below): echo-like
phantom transcripts and full-duplex degradation traced to the room having
more than one uncoordinated audio path, not to a defect in the Realtime
voice pipeline itself. The fix implied by that evidence is topological (one
playback path, one capture point), not a smarter classifier layered on top
of an inherently ambiguous acoustic setup.

## What this changes vs. what it doesn't

This is a **hardware/room-topology** decision, not a resident-voice-pipeline
rewrite. See "Compatibility with the existing implementation" below —
nothing in the current Realtime voice code needed to change for this
decision to be recorded, because the existing code was never written to
assume any particular device topology in the first place.

## Field observation (evidence, not a spec)

**An eMeet-class speakerphone was reported working at approximately 10–12 ft
from the resident with a fan running in the room**, per Michael's live
session report. This is recorded as **one observed field result under those
specific conditions** (that room, that fan, that distance) — **not** a
general performance guarantee, not a spec for every room, and not something
this record claims will reproduce identically elsewhere. Prior forensic
work (`docs/reports/2026-08-25-0245-rooms-401-403-408-forensics.md`)
similarly recorded a field finding — a single eMeet unit serving as both mic
and speaker outperforming a split eMeet-mic/separate-soundbar arrangement —
under the same "supported practical finding, not lab-proven DSP behavior"
framing. Both observations point the same direction and are consistent with
each other, but neither is elevated to a universal hardware claim here.

## The software boundary this implies (for later work)

CAOSCare's software does not need to know today which physical box is
playing Aria, which is playing TV audio, or which mic is capturing — but it
will eventually need to be able to **distinguish these as logical sources**
so it can reason about and control them (e.g. "mute TV audio while Aria is
speaking," "route Aria's playback to the fallback handset instead"). The
smallest clean boundary for that, when it's built, is four logical roles:

- **Aria playback** — the audio CAOSCare's own voice pipeline is producing.
- **TV/media playback** — audio owned by the TV/media source-routing side of
  the room (currently the TV's own speakers; eventually piped through the
  same physical output as Aria playback, per the decision above).
- **Resident microphone capture** — the one capture point Aria listens to.
- **Handset/fallback audio** — the guaranteed-duplex path, independent of
  room acoustics.

This should be built the same way `backend/device_adapters.py` already
separates *what* a room device does (the logical action/value contract) from
*how* a specific transport executes it (mock, Home Assistant, a future
bridge-tablet protocol) — see that file's own docstring for the precedent.
An audio-routing adapter boundary, when built, should let CAOSCare's own
code reason about "Aria playback" / "TV playback" / "mic capture" / "handset"
as stable logical concepts, with **which physical device or transport
implements each one left to configuration** — never a specific eMeet model
or television hardcoded into application logic. **No such adapter exists
yet.** This section describes the target shape for when TV-audio-in-path
work actually starts, not a claim that it's built.

## Explicitly unverified (requires physical hardware)

The following are **not proven, not implemented, and must not be described
elsewhere as working** until tested against real hardware:

- TV headphone-jack / RCA / optical / HDMI-ARC audio-out behavior — which
  output(s) a given TV actually supports, and what electrical/digital path
  would carry that signal to the eMeet.
- eMeet model-specific AEC behavior — how well any specific eMeet unit's
  onboard AEC actually performs once fed a second (TV) audio source, versus
  its currently-tested Aria-only use.
- Electrical/digital TV-audio capture and routing into the eMeet — no wiring,
  adapter, or signal path for this exists yet; it is a described target, not
  a built one.
- TV auto-mute behavior — whether/how a TV's internal speakers can be
  reliably muted in software or hardware once CAOSCare owns its audio.

## Compatibility with the existing resident voice implementation

Inspected before writing this record (2026-08-27), specifically for
conflicts with the decision above:

- `backend/routes/realtime_audio_config.py` (`DEFAULT_VAD`, server-side VAD;
  `DEFAULT_NOISE_REDUCTION`, OpenAI's `far_field` mode) — protocol-level
  configuration, not tied to any device. `far_field` was chosen for
  room/tablet-style mics generically (see the file's own 2026-08-22 comment)
  and remains the right choice for a resident-mounted eMeet under this
  architecture. No conflict.
- `frontend/src/lib/useRealtimeVoice.js` — microphone capture uses
  `getUserMedia({ audio: { echoCancellation, noiseSuppression,
  autoGainControl } })` with **no `deviceId` constraint** — it captures
  whatever the OS/browser has as the default input device. It does not
  select or assume any particular microphone.
- Audio playback (Aria's voice) likewise has no output-device selection
  logic (no `setSinkId` anywhere in the resident voice path) — it plays
  through whatever the OS/browser has as the default output.

**Conclusion: no code conflicts with this architecture, and none needed to
change.** The existing implementation already delegates "which physical
device is the mic/speaker" to the OS/browser default-device layer rather
than hardcoding one — which is exactly the posture this decision requires
going forward. The gap this record identifies (TV audio not yet in the same
path as Aria's audio) is a **room wiring/hardware gap**, not a software
defect — there is currently no TV-audio-into-eMeet signal path for any
software to route through.

## Prior research this record is grounded in

- `docs/reports/2026-08-24-2100-voice-echo-research-and-audio-path-architecture.md`
  — confirmed CAOSCare's own output routing already matches best practice
  and that OpenAI's Realtime API performs no server-side AEC (it is 100%
  client/hardware); identified hardware/software AEC double-processing and
  Linux-only audio-stack caveats as open risks.
- `docs/reports/2026-08-25-0245-rooms-401-403-408-forensics.md` — the
  eMeet-as-single-unit field finding that this record's field observation is
  consistent with.
- `docs/PROJECT_STATE.md`, 2026-08-25 entries — records the decision to
  freeze further voice-classifier tuning pending real field data; this
  record does not reopen that freeze. It documents a room-hardware-topology
  decision, which is a different lever than the classifier work that was
  paused.

## Non-negotiables this record preserves

Generic across rooms/residents; no specific room or resident hardcoded into
this record or implied for future code; CAOSCare owns its own logical
interfaces while external hardware/integration systems remain replaceable
behind configuration; no parallel device/resident/facility model implied —
the future audio-routing boundary described above is meant to sit alongside
the existing `SmartDevice`/`device_adapters.py` pattern, not duplicate it.
