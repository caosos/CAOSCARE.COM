# Voice fundamentals regression matrix — early baseline vs. current

_Lane A. Evidence-only pass. No code changed, no tuning applied._

## Scope and method

Michael's standing claim: *"the simple early resident-voice implementation
appeared materially more reliable than the current complex stack."* This report
establishes what the early implementation actually was, what changed, and which
changes can plausibly cause the observed failure — with a causal mechanism, not
a correlation with "it got more complex."

Sources: full `git log --follow` + diffs on every Realtime file; the dated
entries in `docs/PROJECT_STATE.md`; every session in `db.realtime_diagnostics`
(13 instrumented sessions, 1,162 events); and a **live mint** against the
running backend at 2026-08-23 21:52 UTC to read the config actually being
served rather than trusting source.

Three reference points:

| Ref | Commit | Date | What it is |
|---|---|---|---|
| **EARLY** | `dba0499` | 2026-04-24 | The original simple resident voice. 4 KB backend route, 120-line hook. |
| **MID** | `3a4bd7f` | 2026-08-09 | After the persona/API-shape repairs, before the trust/diagnostics layer. |
| **NOW** | `f092ae5` (live) | 2026-08-23 | Current. Verified live, not read from source. |

**Instrumentation blind spot, stated up front:** `realtimeDiagnostics.js` did
not exist until 2026-08-22. There is **no event-level data whatsoever** for the
EARLY or MID implementations. Michael's recollection is the only evidence that
EARLY was more reliable. Every "was it actually better" claim below is therefore
about *mechanism*, not measured comparison. Nothing here should be read as
proving EARLY was better; it establishes what would have to be true.

---

## The regression matrix

| # | Dimension | EARLY (2026-04-24) | NOW (2026-08-23, live-verified) | Plausible reliability regression? |
|---|---|---|---|---|
| 1 | **Realtime session config** | One `session.update` at `dc.onopen`, flat legacy schema: `instructions`, `voice`, `modalities`, `input_audio_transcription`. Nothing else sent. | One `session.update` at open (nested current schema: `session.type`, `audio.output.voice`, `audio.input.{transcription,noise_reduction,turn_detection}`, `tools`, `tool_choice`) **plus a second mid-session `session.update`** fired from `output_audio_buffer.stopped` to re-enable `create_response`. | **Watch.** The second update sends `audio.input` containing *only* `turn_detection` — omitting `transcription` and `noise_reduction`. If the API replaces rather than deep-merges `audio.input`, `far_field` NR is silently dropped mid-call. Transcription demonstrably survives it (transcripts continue afterward), so a deep merge is likely — but this is unverified and it is the only mutation of audio config that happens while a call is live. |
| 2 | **Mic capture / WebRTC lifecycle** | `getUserMedia({echoCancellation, noiseSuppression, autoGainControl: all true})`. Refs committed before negotiation. No generation guard, no lifecycle listeners. | **Identical audio constraints** (confirmed per-session via `mic_track_settings`). Plus: StrictMode generation token, deferred ref commit, `stop(reason)`, read-only lifecycle diagnostics. | **No.** The capture path itself is byte-identical. The additions are guards and observability; none touch the audio graph. Rules out "the mic setup changed." |
| 3 | **VAD** | **Not configured at all** — no `turn_detection` sent; OpenAI's server default applied (`server_vad`, silence_duration_ms **500**). | Explicit `server_vad`: threshold 0.5, prefix_padding_ms 300, **silence_duration_ms 1000**, `create_response: true`, **`interrupt_response: true`** (added 2026-08-23). | **Yes — strongest candidate.** Two independent deltas: (a) silence window doubled vs. the API default; (b) `interrupt_response` is new *and* correlates with the dead zones (see evidence table). `semantic_vad`+`eagerness:low` was also tried and reverted after causing a 38 s dead zone. |
| 4 | **Noise reduction / browser constraints** | Browser AEC+NS+AGC on. **No server-side `noise_reduction`.** | Same browser constraints, **plus `far_field` server-side NR** (added 2026-08-22 to kill ambient phantom transcripts). Per its own comment, it *"filters audio before VAD/the model see it."* | **Yes — second candidate.** This is the one change that sits upstream of VAD in the audio path and is explicitly suppressive. `far_field` is designed for *raw* far-field mic audio; here it is stacked on top of Chrome's already-aggressive AEC/NS/AGC. Over-suppression below the 0.5 threshold produces exactly "connection healthy, mic healthy, VAD never fires." |
| 5 | **Transcription model** | `whisper-1`. | `gpt-4o-transcribe` (swapped 2026-08-22, single-variable). | **No — but implicated in a different defect.** Transcription runs *after* VAD and cannot suppress turn detection. It is, however, the direct cause of the "transcript doesn't match Aria's answer" symptom (Room 121: "things everywhere." → a correct time-of-day answer). Separate bug, same session. |
| 6 | **Greeting / playback handling** | **No greeting at all.** Aria spoke only after the resident did. | Forced `response.create` at `dc.onopen`, with `create_response: false` for the duration of that one turn, re-enabled on `output_audio_buffer.stopped`. Playback state tracked via `output_audio_buffer.started/stopped/cleared`. | **Watch.** The greeting is the single largest new source of Aria-audio-into-mic echo, and it demonstrably produces phantom turns (Room 121's sibling session: the greeting's own words came back 5.7 s later and were stored as trusted resident speech). It creates the echo pressure that `interrupt_response` then acts on. Not itself a deafness mechanism. |
| 7 | **Barge-in logic** | None. Whatever the API did by default. | `interrupt_response: true` server-side + `classifyUserTurn()` client-side (overlap × segment length × echo resemblance × tiny-fragment streak). | **Yes for `interrupt_response` (see #3).** The client classifier is trust-only — it gates tool execution and the `trusted` flag; it cannot stop VAD. Exonerated as a deafness cause. |
| 8 | **Prompt / preferences / personalization** | **~500 characters.** One paragraph + optional name/preferences/memory line. | **15,380 characters** (~3,845 tokens), live-verified: self-knowledge, time anchor, persona, language, truth discipline, memory-as-reference, attribution, tools, sensitive topics, safety, plus hydrated resident profile. **~30× growth.** | **No — explicitly exonerated.** Server-side VAD operates on the audio stream and is completely independent of the text context. No prompt length can stop `input_audio_buffer.speech_started` from firing. This is the change most tempting to blame and the evidence does not support it for the deafness failure. It remains a plausible cause of *response-quality* drift (over-constrained, tic-avoidant, hedging replies). |
| 9 | **Memory / context injection** | Two flat strings (`preferences`, `memory`) appended to the prompt. | `build_resident_profile_and_memory()`: name discipline, low-vision handling, intake-note reframing, two-bin memory, attribution rules. Every turn also POSTed to `/memory/realtime-turn` and stored in `db.conversations`. | **No** for deafness (same reasoning as #8). **Yes** for truth integrity: known-wrong transcripts are being written as `trusted: true` (Room 121). |
| 10 | **Tools / tool gating** | **0 tools.** | **20 tools**, 14,462 chars of schema (live-verified). Gating: `request_staff_help`, `request_transportation`, `adjust_room_temperature`, `toggle_light`, `toggle_tv`, `update_preferred_name`, `end_call` all refuse on `turn_suspect`. `call_for_help` and **`mark_resting` deliberately ungated** (prompt wording only). | **No** for deafness. Tool dispatch is reactive; it cannot silence VAD. `mark_resting` was the leading suspect after Room 304 — **the Room 121 session disproves it as necessary**: an 83 s terminal dead zone with zero tool calls. `mark_resting` remains a real UX defect (cosmetic `resting` state, no code-level gate) but is not the dead-zone mechanism. |
| 11 | **Persistence / diagnostics** | None. | `logRealtimeEvent()` (14 event types), lifecycle listeners, per-turn immediate persistence, `session_ended` reason capture. | **No.** Fire-and-forget, `keepalive`, all failures swallowed. Pure gain — it is the only reason this analysis is possible at all. **Its gap is the problem:** nothing observes the mic between events. |

---

## Evidence: every instrumented session, ranked by dead-zone severity

A "terminal dead zone" = a gap with **zero `speech_started` events** that never
recovers and ends with the human manually hanging up.

| Session | Start (UTC) | Dur | Turns | Max gap | Terminal? | `far_field` | `interrupt_response` | VAD |
|---|---|---|---|---|---|---|---|---|
| `tr5xurwy` | 08-22 19:11 | 74 s | 7 | 24 s | no | no | no | server |
| `y7muxgva` | 08-22 19:41 | 67 s | 0\* | 12 s | no | no | no | server |
| `x3qhjr15` | 08-22 20:09 | 77 s | 0\* | 18 s | no | no | no | server |
| `y6k3tovh` | 08-22 21:07 | 89 s | 8 | 22 s | no | **yes** | no | server |
| `ltmbbxsp` | 08-22 21:29 | 291 s | 27 | 23 s | no | yes | no | server |
| `zgujz83v` | 08-22 21:46 | 12 s | 4 | 3 s | no | yes | no | server |
| `8y12za2m` | 08-22 21:47 | 115 s | 12 | 27 s | no | yes | no | server |
| `tx9q3o7b` | 08-23 02:01 | 416 s | 34 | 27 s | no | yes | no | server |
| `pc5lblon` | 08-23 02:48 | 93 s | 6 | **45 s** | **YES** | yes | no | **semantic** |
| `pmzwri6n` | 08-23 03:39 | 100 s | 7 | **40 s** | **YES** | yes | **yes** | server |
| `o2jv93b8` | 08-23 14:39 | 508 s | 41 | 33 s | partial (20 s post-`mark_resting`) | yes | **yes** | server |
| `n6kzggub` | 08-23 20:26 | 36 s | 3 | 12 s | no (too short) | yes | **yes** | server |
| `poyo1w56` | 08-23 20:45 | 95 s | 1 | **86 s** | **YES** | yes | **yes** | server |

\* `y7muxgva`/`x3qhjr15` logged `speech_started` but zero transcripts — the
separately-documented broken `include` parameter, fixed 2026-08-22.

### What this table establishes

1. **`mark_resting` is not necessary for the failure.** `poyo1w56` and
   `pmzwri6n` both went terminally deaf with zero tool calls. The Room 304
   conclusion must be widened.
2. **VAD *type* is not the differentiator.** Terminal dead zones occurred under
   `semantic_vad` *and* `server_vad`. Reverting the VAD type did not fix it.
3. **`interrupt_response: true` has the strongest correlation available:
   3 of 4 sessions with it went deaf; 1 of 9 without it did — and that one was
   the `semantic_vad` experiment.**
4. **`far_field` cannot be separated from the failures by this data** — it is
   present in all 3 terminal cases, but also in 6 healthy ones. Only 3
   pre-`far_field` sessions exist and all are under 80 seconds, so its absence
   from that group proves nothing.
5. **Every dead zone begins immediately after an assistant reply and never
   recovers.** Every session starts working. That fingerprint — works, then
   wedges permanently, fresh session works again — is characteristic of an
   adaptive/stateful audio-processing clamp or an input-pipeline wedge, not of
   network, model, prompt, or tool behavior.

### Honest confound

`interrupt_response` was added 2026-08-23 02:49, so the four sessions carrying
it are simply *the four most recent*. The correlation is real but
time-confounded, and n=4. It is a ranked hypothesis, not a proven cause.

---

## Conclusion — the one testable hypothesis

**The regression is in the audio input path, not in the intelligence layer.**

Prompt size (30×), memory hydration, tool count (0 → 20), and tool gating are
all *downstream* of `input_audio_buffer.speech_started`. None of them can
prevent that event from firing. They are exonerated for the reliability
regression Michael is describing, however much they grew.

The EARLY implementation Michael remembers as reliable differed from NOW in
exactly **three** input-path respects, and all three are suppressive or
interruptive:

1. **No server-side `noise_reduction`** — NOW adds `far_field` upstream of VAD.
2. **No explicit `turn_detection`** — NOW sets `silence_duration_ms: 1000`
   (double the API default) with an explicit 0.5 threshold.
3. **No `interrupt_response`** — NOW sets it `true`.

Everything else about capture (`getUserMedia` constraints, WebRTC setup, the
audio graph) is unchanged since April.

**H1 (test first): `interrupt_response: true` wedges input handling after an
echo-driven interruption.** Best correlation in the data (3/4 vs 1/9); a
concrete mechanism (mid-playback truncation bookkeeping); newly added; and the
forced greeting supplies exactly the echo pressure needed to trigger it. It is
also a **one-field, one-line revert**.

**H2 (test second): `far_field` NR stacked on Chrome's AEC/NS/AGC
over-suppresses the resident below the VAD threshold.** Correct mechanism,
correct position in the pipeline (pre-VAD, by its own documentation), but the
data cannot currently separate it.

---

## Proposed next steps — for the lead to approve, NOT applied here

### Step 0 (blocking, and the actual recommendation): close the blind spot first

Both the Room 304 report and the Room 121 report reached the same wall: **there
is no signal distinguishing "the resident was silent" from "the resident spoke
and it was not detected."** Until that exists, any A/B is judged only by
Michael's subjective impression, and a negative result cannot be trusted.

The smallest thing that closes it: attach a `Web Audio AnalyserNode` to the
already-captured local stream and log an RMS level every ~2 s as a
`mic_level` diagnostic event. No audio content, no transcript, no new
permission, no change to the audio graph the peer connection uses (an
`AnalyserNode` on a `MediaStreamSource` is a passive tap). Roughly 30 lines in
a new `realtimeMicLevel.js` plus three lines of wiring.

With that, the next dead zone answers itself in one query:
- RMS spikes during the dead zone → audio reached the browser, OpenAI's VAD did
  not fire → server-side (H1/H2 territory).
- RMS flat during the dead zone → the mic track stopped delivering → a browser/
  device-level problem, and both H1 and H2 are wrong.

This is diagnostic-only and reversible, but it touches the live Realtime stack,
so per Lane A's mandate it is **proposed, not built**.

### Step 1: single-variable A/B, in this order

Per the standing `one controlled change → real-room test → forensic report →
keep or revert` loop:

1. **Remove `interrupt_response: true`** from `DEFAULT_VAD`
   (`backend/routes/realtime_audio_config.py`). One field. Restores the exact
   config that ran `tx9q3o7b` — 416 s, 34 turns, max gap 27 s, no dead zone.
   Accept cost: genuine barge-in gets weaker. Test for a dead zone across at
   least 3 minutes of real conversation.
2. If the dead zone recurs: **remove `noise_reduction`** from the resident
   session (return to EARLY's behaviour: browser AEC/NS/AGC only). Accept cost:
   ambient phantom transcripts may return — which is a *visible, recoverable*
   defect, whereas going deaf is not.
3. If it still recurs: **drop `silence_duration_ms` to the API default 500**.

**A parallel minimal-baseline voice stack is not warranted.** The EARLY hook and
the current one share an identical capture path; the entire difference is three
values in one config dict. Rebuilding a second stack would test nothing that
reverting three fields does not test, and would add a maintenance burden the
project's own rules discourage. Recommend the single-variable ladder instead.

---

## Two defects found in passing — flagged, not fixed

Both are in files Lane A does not own for edits this round.

1. **Known-wrong transcripts persist as `trusted: true`.** Room 121 stored
   `"things everywhere."` as trusted resident speech while Aria (correctly)
   answered a request for the time. `classifyUserTurn()` only measures playback
   overlap; there was none, so it returned `no_overlap`. The intended catch,
   `transcriptionConfidence()`, no-ops because the API returns no logprobs over
   this path (0/34 turns in Room 304, `null` here). Under the project's
   provenance rules a fabricated user utterance should not become durable
   memory. `realtimeMessageHandler.js` — needs a design decision, not a patch.

2. **Delayed echo bypasses the trust boundary entirely.** In `n6kzggub`, Aria's
   own greeting line came back through the mic **5.7 s after** her
   `response.done` — after `assistant_speaking` had gone false — was classified
   `no_overlap`, stored `trusted: true`, and she answered her own question. The
   echo-resemblance check exists but only runs for turns that overlapped
   playback, so room reverb / speaker tail arriving after
   `output_audio_buffer.stopped` is never checked against
   `lastAssistantText`. A short post-playback grace window would cover it.

3. **`mark_resting` still has no code-level gate** (carried forward from the
   Room 304 report, unchanged). It is no longer the leading dead-zone suspect,
   but it remains ungated by design and is the only consequential tool whose
   entire protection is prompt wording.

---

## Files inspected

Frontend: `useRealtimeVoice.js` (257), `realtimeMessageHandler.js` (281),
`realtimeSessionUpdate.js` (59), `realtimeDeviceTools.js` (174),
`realtimeOperationsTools.js` (213), `realtimeDiagnostics.js` (39),
`realtimeLifecycleDiagnostics.js` (43), `RealtimeChatScreen.jsx` (165),
`AriaVoice.jsx`.

Backend: `realtime.py` (308), `realtime_audio_config.py` (24),
`realtime_companion_prompt.py` (240), `realtime_companion_memory.py` (102),
`realtime_tools.py` (298), `realtime_tools_operations.py` (222),
`realtime_aria_tools.py` (88), `realtime_facility.py` (60),
`realtime_diagnostics.py` (52), `realtime_memory_ingest.py` (90),
`realtime_self_knowledge.py` (110), `operational_provenance.py` (49).

History: `dba0499`, `77125a6`, `48ee0c0`, `98f5955`, `6b9445e`, `bff3111`,
`77b3864`, `f1f9620`, `1154bf5`, `6d6d9ad`, `fded130`, `4878047`, `da63c02`,
`229280b`, `813669b`, `3a4bd7f`, `fa6b7ac`.

**No production file was created or modified by this lane. Line counts above are
current-state observations, not changes.**
