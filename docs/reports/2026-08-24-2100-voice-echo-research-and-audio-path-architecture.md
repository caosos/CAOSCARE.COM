# Voice echo/full-duplex — research findings, audio-path architecture, and controlled-test plan

_Issue #22 (SIM-6). Research pass + ONE controlled, purely additive telemetry
change. No VAD/audio-setting change, no restart, no DB mutation, no SIM-7
files touched._

Michael's directive: stop tuning blindly, research how mature systems solve
full-duplex/AEC first, document CAOSCARE's actual audio path, and fix the
audio path itself (not just the downstream transcript classifier) wherever
evidence supports it.

---

## RESEARCH FINDINGS

### 1. How mature systems solve this

Every production browser voice stack investigated (LiveKit, Daily-class
WebRTC agents, Twilio Video, the OpenAI Realtime reference/community
implementations) relies on the **same underlying mechanism**: the browser's
own built-in AEC (Chromium/WebRTC's AEC3, part of libwebrtc's Audio
Processing Module — high-pass filter → AEC3 → noise suppression → AGC2, in
that fixed order), triggered by `getUserMedia({ audio: { echoCancellation:
true } })`, working because the assistant's remote audio is played through a
mechanism the browser's own audio pipeline can see and use as its cancellation
reference. Nobody has invented a proprietary echo-cancellation algorithm at
the application layer — they all lean on the browser/OS/hardware doing it,
and their engineering effort goes into **not accidentally defeating it**.
[Switchboard: How WebRTC AEC3 Works](https://switchboard.audio/hub/how-webrtc-aec3-works/),
[Fora Soft: The WebRTC audio pipeline end-to-end](https://www.forasoft.com/learn/audio-for-video/articles-audio/webrtc-audio-pipeline-end-to-end),
[LiveKit: How echo cancellation works in WebRTC](https://www.protoface.com/blog/how-does-echo-cancellation-work-in-webrtc-for-livekit-and-browser-based-ai-avatars).

### 2. Which architecture most closely matches CAOSCARE

**CAOSCARE's own architecture already matches the proven pattern**, confirmed
by reading the actual source (`frontend/src/lib/useRealtimeVoice.js`,
`RealtimeChatScreen.jsx`), not assumed:

- Mic: `getUserMedia({ audio: { echoCancellation: true, noiseSuppression:
  true, autoGainControl: true } })` — the standard boolean-constraint form.
- Assistant audio: `pc.ontrack = (ev) => { audioElRef.current.srcObject =
  ev.streams[0]; }`, rendered via `<audio ref={localAudioElRef} autoPlay
  playsInline className="hidden" />` in `RealtimeChatScreen.jsx:142`. **This
  is the single most important architectural fact**, because it is also the
  one thing the research consistently flags as the difference between
  working and broken AEC in other systems (next section).

This is the exact shape of OpenAI's own community reference implementations
(webrtcHacks' single-file demo, the `openai-realtime-webrtc` demo) and of
LiveKit's/Daily-class browser SDKs.

### 3. Which pieces CAOSCARE currently does differently

Nothing found in the **output-routing architecture itself**. What's
different is narrower and was pinned down by reading the code, not guessed:

- **A one-time `AudioContext` "unlock" exists** (`Kiosk.jsx:96-100`), created
  and resumed on first user gesture to satisfy Chrome's autoplay policy for
  the TTS announcement/`<audio>` elements. Checked explicitly: it is **never**
  connected to any source or destination — `grep audioCtxRef` in that file
  returns only the three lines that create/resume it. **This is not the
  documented AudioContext-bypasses-AEC bug** (see pitfall below) — ruled out
  by reading the code, not assumed.
- **Three separate `new Audio(dataURI)` elements exist** for TTS announcements
  (`ResidentsTab.jsx:43`, `Kiosk.jsx:230`, `Kiosk.jsx:346`), independent of
  the Realtime `<audio>` element. Not proven relevant to the echo defect, but
  flagged as a real architectural difference from a single-audio-element
  reference implementation, worth keeping in mind if a future session shows
  echo correlated with an announcement firing mid-call.
- **No `echoCancellationType` constraint is requested** — CAOSCARE takes
  Chrome's default AEC engine selection rather than declaring one explicitly.
- **No advanced/Google-specific constraints** (`googEchoCancellation2`,
  `googAutoGainControl2`, etc.) are requested — plain boolean constraints only.
- **`MediaStreamTrack.getSettings()` is sampled exactly once**, at connect —
  confirmed by `grep getSettings` returning a single call site
  (`useRealtimeVoice.js:139`). No `getConstraints()`/`getCapabilities()` call
  exists anywhere in the codebase.
- **VAD config is CAOSCARE's own** (`server_vad`, threshold 0.5,
  `silence_duration_ms: 1000`, `interrupt_response: true`) — this is a
  session-config choice downstream of AEC, not an AEC difference, but see
  finding 4 below for why it still matters.

### 4. Known browser/Linux/eMeet pitfalls that apply

- **Confirmed, most load-bearing pitfall in general (does NOT apply to
  CAOSCARE's code as written):** playing remote audio through Web Audio's
  `AudioContext.destination` instead of an `<audio>` element's `srcObject`
  defeats Chromium's AEC entirely. Chromium's echo canceller specifically
  recognizes audio routed through an `HTMLAudioElement`/`<video>` as "remote
  participant audio" and uses it as the cancellation reference; audio routed
  directly to `AudioContext.destination` isn't tagged that way, so nothing is
  cancelled. Directly documented in a real, filed Chromium bug (Issue
  687574) reported via Twilio's video SDK, and independently confirmed in a
  from-scratch technical write-up. CAOSCARE was checked against this
  specifically and does not do it.
  [dev.to: Echo Cancellation with Web Audio API and Chromium](https://dev.to/focused_dot_io/echo-cancellation-with-web-audio-api-and-chromium-1f8m),
  [twilio-video.js#323 / Chromium 687574](https://github.com/twilio/twilio-video.js/issues/323).
- **OpenAI's Realtime API does zero server-side echo cancellation.**
  Confirmed from OpenAI's own documentation: *"echo cancellation needs to be
  done on the client device, while other kinds of audio processing can
  usefully be done server-side."* `input_audio_noise_reduction`
  (`near_field`/`far_field`, what CAOSCARE calls `far_field`) is a **separate**
  feature for ambient/background noise on writes to the input buffer — not
  echo, and not a safety net if local AEC under-performs. Whatever residual
  echo survives the browser/hardware is exactly what the model sees; there is
  no second chance upstream. [OpenAI Realtime client events reference](https://developers.openai.com/api/reference/resources/realtime/client-events).
- **Hardware/software AEC double-processing is a real, named, documented
  failure class** for exactly this class of device. USB conferencing
  speakerphones (the eMeet family included) run their **own onboard DSP echo
  cancellation** (eMeet calls theirs "VoiceIA"). Established guidance from
  the conferencing-hardware world: *"decide which component — hardware or
  software — performs AEC, and make sure the other side's corresponding
  features are off... if relying on software-based DSP, hardware should
  output an unprocessed stream."* Zoom/Teams handle this by detecting a
  device that self-identifies as an "Echo-Cancelling Speakerphone" over USB
  and deferring to it automatically. **Chrome does expose a lever for this**
  — `echoCancellationType: "system"` (falls back to `"browser"` if
  unavailable) — but Google's own documentation states platform support as
  **macOS and Windows only**; it is not documented for Linux. This machine is
  Linux (`6.8.0-138-generic`), so this specific lever is likely not directly
  actionable from CAOSCARE's own `getUserMedia` call — stated here as a real
  limitation, not swept under the rug. [Chrome for Developers: More native
  echo cancellation](https://developer.chrome.com/blog/more-native-echo-cancellation),
  [Pawpaw: DSP Hardware vs. Software in Remote Meetings](https://www.pawpaw.cn/en/news/article/2025-07-15-dsp-hardware-vs-software-in-remote-meetings-who-ensures-sound-quality/).
- **PipeWire's own separate echo-cancel module is opt-in, not default.**
  Its docs describe a real echo-cancel module (`aec/libspa-aec-webrtc`) but
  it must be manually added to PipeWire's config — nothing indicates it's
  active on this machine by default, meaning (absent that manual config) the
  **only** AEC actually running is whatever Chromium's own software AEC3
  does per-tab, plus whatever the eMeet does on its own at the hardware
  level before the signal is even digitized by the OS. [PipeWire: Echo
  Cancel module docs](https://docs.pipewire.org/page_module_echo_cancel.html).
- **A real, mature-framework-documented finding on VAD sensitivity:**
  *"The OpenAI VAD seems to be more sensitive to background noise than the
  default phrase endpointing implementation in Pipecat"* — Pipecat (a
  well-known production voice-agent framework) deliberately uses smoothed,
  energy-based endpointing that "ignores short spikes in audio even if they
  have a fairly high speech confidence rating," specifically to avoid
  exactly this class of false-positive-turn problem. [Latent Space: OpenAI
  Realtime API — The Missing Manual](https://www.latent.space/p/realtime-api).
  **Tested against CAOSCARE's own Room 404 data (see next section) — the
  simple version of this pattern does not cleanly apply here.**
- **A real, current (Sept 2025) open issue in LiveKit's own JS SDK**
  reproduces literally the same class of symptom — "brief echo/feedback
  audible when the call starts, even with echo cancellation enabled... after
  a short period, echo cancellation appears to work correctly" — on
  `Chrome 139 / Linux`. No root cause or fix was published in the issue as
  fetched, but it independently corroborates that **even a mature,
  purpose-built framework sees exactly this failure mode on this OS/browser
  combination**, and that it can be transient/converging rather than a fixed
  code defect. [livekit/client-sdk-js#1646](https://github.com/livekit/client-sdk-js/issues/1646).
- **Chromium exposes free, built-in AEC diagnostics that CAOSCARE has never
  used**: `chrome://webrtc-internals`, opened during a live call, has an
  option to record an `aec_dump` — an archive containing the actual
  pre-cancellation reference and post-cancellation microphone audio, openable
  in any audio editor, that would show directly whether/how much
  cancellation is happening, with zero code changes. [webrtcHacks:
  Troubleshooting Unwitting Browser Experiments](https://webrtchacks.com/troubleshooting-unwitting-browser-experiments-al-brooks/).

### 5. Recommended proven architecture

**Keep the current output-routing architecture — it already matches the one
pattern that matters most, confirmed by reading the code.** Do not rebuild
it. The recommended next steps, in order of how established/low-risk they are:

1. **Free, zero-code**: capture a `chrome://webrtc-internals` `aec_dump`
   during Michael's next real-room test. This directly answers "is local AEC
   engaging, and how much residual survives" — the single most
   evidence-establishing thing available, and it requires no CAOSCARE code
   at all.
2. **Already shipped this pass**: the telemetry addition below, so the next
   real-room test has exact numbers (VAD segment duration, time since Aria's
   audio genuinely stopped) instead of manual timestamp cross-referencing.
3. **Deliberately NOT shipped this pass** (see honest negative finding
   below): a `classifyUserTurn()` behavior change. Evidence-tested against
   real Room 404 data and found to carry a real false-positive risk against
   genuine resident speech — holding for a decision after (1) and (2)
   produce real data from a fresh test, per the standing one-controlled-
   change rule.
4. **A genuinely hardware/OS-level question for Michael, not a CAOSCARE code
   change**: check whether the eMeet has its own control app/DIP switch/
   firmware setting to toggle its onboard AEC, since Linux Chrome has no
   documented lever (`echoCancellationType` is Mac/Windows only) to
   coordinate with it from the browser side.

### 6. Sources

- [Switchboard: How WebRTC AEC3 Works](https://switchboard.audio/hub/how-webrtc-aec3-works/)
- [Fora Soft: The WebRTC audio pipeline end-to-end](https://www.forasoft.com/learn/audio-for-video/articles-audio/webrtc-audio-pipeline-end-to-end)
- [Chromium AEC3 source (echo_canceller3.h/.cc)](https://chromium.googlesource.com/external/webrtc/+/master/modules/audio_processing/aec3/echo_canceller3.h)
- [dev.to: Echo Cancellation with Web Audio API and Chromium](https://dev.to/focused_dot_io/echo-cancellation-with-web-audio-api-and-chromium-1f8m)
- [twilio-video.js#323 (Chromium Issue 687574)](https://github.com/twilio/twilio-video.js/issues/323)
- [Chrome for Developers: More native echo cancellation (`echoCancellationType`)](https://developer.chrome.com/blog/more-native-echo-cancellation)
- [Pawpaw: DSP Hardware vs. Software in Remote Meetings](https://www.pawpaw.cn/en/news/article/2025-07-15-dsp-hardware-vs-software-in-remote-meetings-who-ensures-sound-quality/)
- [PipeWire: Echo Cancel module](https://docs.pipewire.org/page_module_echo_cancel.html)
- [OpenAI Realtime client events reference (client-side AEC statement)](https://developers.openai.com/api/reference/resources/realtime/client-events)
- [Latent Space: OpenAI Realtime API — The Missing Manual](https://www.latent.space/p/realtime-api)
- [livekit/client-sdk-swift#916 — AEC regression, agent hears itself](https://github.com/livekit/client-sdk-swift/issues/916)
- [livekit/client-sdk-js#1646 — echo feedback at call start on Chrome/Linux](https://github.com/livekit/client-sdk-js/issues/1646)
- [LiveKit / Protoface: How echo cancellation works in WebRTC](https://www.protoface.com/blog/how-does-echo-cancellation-work-in-webrtc-for-livekit-and-browser-based-ai-avatars)
- [webrtcHacks: Troubleshooting Unwitting Browser Experiments (aec_dump)](https://webrtchacks.com/troubleshooting-unwitting-browser-experiments-al-brooks/)
- [eMeet OfficeCore M2/Luna/M0 Plus product pages (VoiceIA DSP AEC)](https://emeet.com/products/speakerphone-m2)

---

## Current CAOSCARE audio path, traced from source (not assumed)

| Question | Answer, with location |
|---|---|
| `getUserMedia` constraints | `{ echoCancellation: true, noiseSuppression: true, autoGainControl: true }` — `useRealtimeVoice.js:127-129`. No `deviceId`, no advanced constraints, no `echoCancellationType`. |
| Actual `MediaStreamTrack.getSettings()` | Captured once at connect, logged as `mic_track_settings`. Room 404: `autoGainControl:true, echoCancellation:true, noiseSuppression:true, channelCount:1, sampleRate:48000, sampleSize:16`, fixed `deviceId`/`groupId`. |
| `getConstraints()`/`getCapabilities()` | Never called anywhere in the codebase (grepped, confirmed absent). |
| Output routing | `pc.ontrack` → `<audio autoPlay playsInline srcObject={remoteStream}>` — `useRealtimeVoice.js:145-148`, rendered `RealtimeChatScreen.jsx:142`. No `setSinkId`, no explicit output device selection — plays to whatever the browser's default communications device is. |
| Web Audio / AudioContext use | One inert "unlock" `AudioContext`, created+resumed on first gesture, never connected to a source or destination (`Kiosk.jsx:96-100`). Confirmed via `grep audioCtxRef` — 3 lines total, none downstream. **Not** the AudioContext-bypasses-AEC pattern. |
| Other concurrent audio elements | 3 separate `new Audio(base64Mp3)` TTS-announcement elements exist (`ResidentsTab.jsx:43`, `Kiosk.jsx:230,346`), independent of the Realtime `<audio>` element. |
| Hardware AEC active? | eMeet devices document onboard DSP echo cancellation (VoiceIA) as a hardware feature. Whether it's actually engaging on this exact unit/session is **NOT OBSERVABLE** from any browser-side API. |
| Software+hardware AEC conflict possible? | Plausible per documented industry pattern (hardware/software double-processing); **not provable or disprovable** from current telemetry. `chrome://webrtc-internals` is the free, zero-code way to check. |
| PipeWire-level AEC | No evidence it's configured — its echo-cancel module is opt-in, not default, per PipeWire's own docs. |
| Explicit constraints CAOSCARE differs from browser defaults | None beyond the standard three booleans — no aggressive/unusual constraint set was requested. |

---

## Honest negative finding: why `classifyUserTurn()` was NOT changed this pass

The Room 404 report (posted to this issue 2026-08-24) pinpointed two
structural gates in `classifyUserTurn()` that let all three of that session's
phantom turns through. The obvious next step looked like: widen those gates
and/or replace the exact-substring resemblance check with a fuzzy/word-overlap
one. **Tested against the actual Room 404 transcript before writing any
code, this has a real false-positive cost:**

A simple word-overlap-ratio check (fraction of the turn's words present in
Aria's immediately preceding utterance) correctly flags all three phantoms —
"Of course, honey." (2/3 words match "Of course, Harold...", ratio 0.67),
"you need." (2/2 match, ratio 1.0), "Mine's all set now." (3/4 match against
"Your reminder's all set now...", ratio 0.75) — **but at the same threshold
it also flags "Bake chicken thighs?"**, a genuine resident question from the
same session, at an identical 0.67 ratio against Aria's own "...Baked Chicken
Thighs, Rice Pilaf..." A resident naturally repeating or confirming what
Aria just said is common and legitimate, especially in this population —
and word-overlap alone cannot distinguish that from an echo.

This also explains, retroactively, why the original narrow scoping
(overlap-required, ≤2-words-only) existed in the first place — it wasn't an
oversight, it was a real (if incomplete) false-positive mitigation.

A **duration-based** pre-filter (Pipecat's "ignore short spikes" pattern) was
also checked against Room 404's actual segment durations and does not
cleanly separate the phantoms (1.7-2.4s) from genuine short replies like
"Okay." (1.25-1.9s) or "Nice." (1.4s) in this session — durations overlap.

**Conclusion: no cheap, low-risk classifier change survived testing against
real data this round.** Shipping one anyway would trade a proven defect
(phantom trusted echoes) for an unproven one (real resident speech
incorrectly distrusted) without evidence either is net better. The telemetry
below is what makes that decision testable next time, instead of guessed.

---

## What was implemented this pass (the ONE controlled change)

**`frontend/src/lib/realtimeMessageHandler.js`: 281 → 299 lines.** Purely
additive diagnostic logging, no VAD/audio-setting change, no classification
behavior change:

- `output_audio_buffer.started`/`.stopped`/`.cleared` now logged as their own
  diagnostic events (previously only folded into whichever unrelated event
  happened next) — independent, queryable playback-boundary timestamps.
- `speech_segment_ms` (VAD `speech_started`→`speech_stopped` duration) and
  `ms_since_assistant_stopped` (time since Aria's audio genuinely stopped
  playing) now logged on every `user_transcript` event.
- Realtime `error` events, previously UI-only and invisible to any later
  database query, are now persisted as `realtime_error`.

Committed and pushed: `c046154`. Verified compiling cleanly against the live
supervised frontend dev service (`caoscare-frontend-dev.service`, hot-reload
— 4 successive recompiles after each edit, zero new errors/warnings beyond
two pre-existing, unrelated ESLint warnings in `Admin.jsx`/`FacilitiesTab.jsx`).
No restart performed.

No other production file was created or modified this pass. No SIM-7 files
touched. No database record changed.

---

## Controlled test plan — ready to run, NOT run by this pass

Per Michael's A/B/C structure, now with the new telemetry available and the
free `chrome://webrtc-internals` capture recommended alongside it. **This
requires Michael's live voice in the room — it cannot be executed or
fabricated by this pass.**

- **Step 0 (do this first, zero code):** open `chrome://webrtc-internals` in
  a second tab before starting a Realtime session, enable the AEC dump
  option, run test A below, then inspect the dump.
- **A. Aria-only** — Aria speaks continuously, Michael silent. Acceptance:
  no `user_transcript` events at all, or only `uncertain_fragment`/
  `no_overlap`-with-near-zero-resemblance ones that stay `trusted:false`.
- **B. Full duplex** — Michael speaks over Aria. Acceptance: `speech_started`
  fires with `assistant_speaking:true`, a real `coherent_barge_in` turn is
  captured, transcript is accurate, mic is never muted.
- **C. Far field** — repeat at the eMeet, ~10ft away, walking, doorway/
  bathroom position, matching the known-good ChatGPT control test's
  conditions on the same hardware.

After each run, the new `speech_segment_ms`/`ms_since_assistant_stopped`
fields and the independent `output_audio_buffer_started`/`stopped` events
answer, with real numbers instead of inference, whether phantom turns
cluster at short durations, short delays after playback, or neither —
which determines whether any classifier change is even the right lever
versus a genuinely audio-path-level one.
