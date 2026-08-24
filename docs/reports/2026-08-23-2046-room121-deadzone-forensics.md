# Room 121 dead-zone forensic report — a NEW session, not the Chauncey/304 case

**Session:** `rt_poyo1w56_1787517909074`
**Resident:** `res_6f22f68e3abd` — name on file `michael`, Room **121**, kiosk `kio_028d1bfba6bd`
**Duration:** 2026-08-23 20:45:09.880 – 20:46:45.214 UTC (3:45–3:46 PM local), **1m35s**
**Surface:** resident kiosk (`RealtimeChatScreen.jsx`, the screen that renders
`Live · idle` / "Speak any time — I'm listening")
**Runtime config, verified live** by minting a fresh session against the running
backend at 21:52 UTC (not read from source): `server_vad` {threshold 0.5,
prefix_padding_ms 300, silence_duration_ms 1000, create_response true,
**interrupt_response true**}, `far_field` noise reduction, `gpt-4o-transcribe`,
20 tools, 15,380-char instructions. Mic constraints for this exact session
confirmed from its own `mic_track_settings` event: echoCancellation,
noiseSuppression, autoGainControl all `true`, 48 kHz, mono.

## This is not the previously documented session

Michael's reported symptom matches
`2026-08-23-1448-room304-morning-forensics.md`, but this is a **different,
newer session**:

| | Room 304 morning | **Room 121 (this report)** |
|---|---|---|
| Session | `rt_o2jv93b8_1787495975387` | `rt_poyo1w56_1787517909074` |
| Resident / room | Chauncey `res_f2afcf233c09` / 304 | michael `res_6f22f68e3abd` / **121** |
| Start (UTC) | 14:39:38 | **20:45:09** |
| Duration | 8m28s | **1m35s** |
| Real USER turns | ~29 of 41 | **1 of 1** |
| `mark_resting` fired | **yes** — immediately preceded the dead zone | **no — zero tool calls all session** |
| Dead zone | 20s | **83s** |

The `mark_resting` explanation from the Room 304 report **does not apply
here**. There were no tool calls of any kind in this session. Whatever causes
the listening-but-deaf state does not require `mark_resting` — that finding
should be treated as corrected/widened, not repeated.

## Full chronological event stream (complete, nothing elided)

```
20:45:09.880  mic_track_settings   echoCancellation:true noiseSuppression:true
                                   autoGainControl:true 48kHz mono
20:45:10.503  pc_connection_state  connecting
20:45:10.801  pc_ice_connection_state  connected
20:45:11.418  pc_connection_state  connected
20:45:12.467  response_created                       [forced greeting]
20:45:13.564  assistant_transcript "Good afternoon, michael. What's on your
                                    mind right now?"
20:45:13.571  response_done
        --- 5.4s ---
20:45:18.994  speech_started       assistant_speaking=false   [REAL turn 1]
20:45:20.633  speech_stopped       assistant_speaking=false
20:45:20.636  response_created                       [server auto create_response]
20:45:21.246  user_transcript      "things everywhere."
                                   turn_class_reason=no_overlap, trusted=TRUE
20:45:21.963  assistant_transcript "Sure, michael. It's 3:45 in the afternoon
                                    right now."
20:45:22.169  response_done
        ================ 83.0 SECONDS, ZERO EVENTS ================
20:46:45.214  session_ended        reason: ui_end_call_button
```

That is the entire session. 14 diagnostic events.

## Turn classification

- **Real USER turns: 1** — the segment at 20:45:18.994–20:45:20.633 (1.64s of
  speech, no playback overlap).
- **Phantom / echo turns: 0.** No turn began while Aria's audio was playing
  (`assistant_speaking` was `false` at the only `speech_started`). Unlike Room
  304 and Room 121's own earlier session, echo was not a factor here.
- **Tool calls: 0.** No `mark_resting`, no `end_call`, no operational request.
  Nothing fabricated reached a durable record from a tool this session.

## Did the visible transcript match what Aria actually responded to? NO

This session contains the clearest example yet of the divergence flagged in
the Room 304 report, and it is the exact symptom Michael described.

| | |
|---|---|
| On screen / saved as the resident's words | **"things everywhere."** |
| What Aria actually answered | **"Sure, michael. It's 3:45 in the afternoon right now."** |

"things everywhere." cannot produce a time-of-day answer. The native
speech-to-speech Realtime model reasoned over the raw audio and correctly
heard a request for the time; the separate `gpt-4o-transcribe` pass, given the
same 1.64 seconds of audio, produced unrelated words. Aria's reply was correct
for what was actually said. **The transcript was wrong, not the response.**

Architecture note (already established, re-confirmed here): the conversational
model and the transcription model are two independent models fed the same
audio. They are not guaranteed to agree, and the on-screen transcript is the
*less* reliable of the two.

### Data-integrity consequence — new, and worth flagging

`db.conversations` now holds, for resident `res_6f22f68e3abd`:

```json
{"role":"user","content":"things everywhere.","trusted":true,
 "session_id":"rt_poyo1w56_1787517909074","room":"121",
 "created_at":"2026-08-23T20:45:21.244381+00:00"}
```

A known-wrong transcript was persisted as **`trusted: true`** resident speech
and is now durable memory/context for future sessions. The trust classifier
correctly reports `no_overlap` — it only ever measures playback overlap, and
there was none. It has no signal for "the transcription model and the
conversational model disagree," which is precisely the failure that occurred.
`transcriptionConfidence()` would have been the intended catch, but the API
returns no logprobs over this path (`confidence: null` here, and 0/34 turns in
Room 304), so it no-ops.

This is a truth-integrity issue under the project's own provenance rules, not
merely a display bug. Flagged for the lead; **no code changed.**

## Termination cause — exactly determined

`session_ended` reason **`ui_end_call_button`**. Michael pressed End Call
himself, 83.0 seconds after the last system event. This is not a crash, not a
disconnect, not a model-initiated hangup.

Connection health across the whole dead zone: the last transport event was
`pc_connection_state: connected` at 20:45:11.418, and the read-only lifecycle
listeners (`realtimeLifecycleDiagnostics.js`) logged **no** `failed`, `closed`,
`ice_failed`, `datachannel_closed`, `datachannel_error`, or
`page_hidden_or_closed` at any point. Those listeners are known to work — they
are what captured `ui_end_call_button` itself. The WebRTC peer connection was
healthy for the entire dead zone.

Client status during the dead zone was `live` (set by the last `response.done`
at 20:45:22.169 and never changed afterward), which the kiosk renders as
`Live · idle` / "Speak any time — I'm listening." **The UI was telling the
truth about its own state and lying about reality** — exactly what Michael saw.

No `error` event reached the client either: `realtimeMessageHandler.js` sets
status to `error` on any Realtime `error` message, and the screen would have
read "Something went wrong." It did not.

## What can and cannot be concluded

**Established:**
1. VAD stopped producing `input_audio_buffer.speech_started` for 83 seconds
   and never recovered inside the session.
2. The transport was healthy throughout; no error, no disconnect, no teardown.
3. No `mark_resting`, no tool call, and no client-side state change of any kind
   occurred at or before the onset — the previously suspected trigger is absent.
4. The dead zone is **terminal within a session**: it began after the first
   assistant reply and lasted until the human gave up.

**Not established, and not guessable with current instrumentation:**
whether the resident's speech reached OpenAI and was not detected, or never
left the browser at all. There is still no mic-level signal, no input-audio
heartbeat, and no server acknowledgment of received audio. This is the same
blind spot the Room 304 report identified; it has not been closed, and it is
now the single thing blocking a root cause. See the companion regression
matrix report for the specific, small instrumentation proposed to close it.

## The immediately preceding session, for contrast

`rt_n6kzggub_1787516799647` — same resident, same kiosk, 19 minutes earlier
(20:26:42–20:27:18, 36s, 3 turns, ended `ui_end_call_button`). It shows the
*other* failure mode and no dead zone:

```
20:26:45.972  assistant "Good afternoon, michael. What's on your mind?"
20:26:46.788  speech_started  assistant_speaking=TRUE      [greeting echo]
20:26:48.432  user      "Hima"        uncertain_fragment, trusted=false
20:26:48.706  assistant "Good afternoon, michael. What's on your mind today?"
20:26:54.380  speech_started  assistant_speaking=false
20:26:56.722  user      "What's on your mind?"  no_overlap, trusted=TRUE
20:26:58.161  assistant "Well, I'm thinking about how I can be here with you..."
```

The turn at 20:26:56 — "What's on your mind?" — is Aria's **own greeting line
played back into the mic**, captured 5.7s after her `response.done` and
therefore after `assistant_speaking` had gone false. It was classified
`no_overlap`, stored `trusted: true`, and Aria answered her own question. The
echo-resemblance check in `classifyUserTurn()` never ran, because the
classifier only considers resemblance for turns that overlapped playback.

Delayed acoustic echo (room reverb / speaker tail arriving after
`output_audio_buffer.stopped`) is not covered by the current trust boundary.
Also flagged, not changed.

## Concise answer to the questions asked

- **Same session as before?** No. New session, new resident, new room, ~6 hours later.
- **Duration:** 1m35s.
- **Real turns:** 1.
- **Phantom turns:** 0 in this session (2 in the sibling session 19 minutes earlier).
- **Termination cause:** `ui_end_call_button` — Michael ended it manually after
  83 seconds of no response. Transport healthy, no error, no model-initiated end.
- **Did the transcript match Aria's actual response?** No. Transcript
  "things everywhere."; Aria answered a request for the time. The audio model
  understood correctly; the transcript model did not. The wrong transcript was
  persisted as trusted resident speech.
