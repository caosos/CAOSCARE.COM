# Morning Chauncey/Room 304 forensic report

**Session:** `rt_o2jv93b8_1787495975387` — Chauncey (`res_f2afcf233c09`), Room 304
**Duration:** 14:39:38–14:48:06 UTC (9:39–9:48 AM local), 8m28s
**Runtime config, verified live:** `server_vad` {threshold 0.5, prefix_padding_ms 300,
silence_duration_ms 1000, create_response true, interrupt_response true},
`far_field` noise reduction, `gpt-4o-transcribe`, mic constraints
(echoCancellation/noiseSuppression/autoGainControl all true, confirmed from
this session's own `mic_track_settings` event).

## Summary

- ~29 of 41 USER turns were real and correctly transcribed.
- 4 turns were confirmed wrong **by Michael himself, in real time**:
  "Pete," "small," "sleep," "upset" — each immediately disputed.
- A bare `"."` and two `"Hello"`s echoed Aria's own greeting audio.
- `mark_resting` fired incorrectly (see below) — the intent-inversion
  protection is confirmed still insufficient.
- A 20-second period with zero `speech_started` events followed the
  `mark_resting` call, ending when Michael hit End Call. Cause unproven —
  no instrumentation currently exists to tell "resident was silent" apart
  from "resident spoke and wasn't detected."
- All 3 real operational tool calls this session (AC/maintenance, kitchen
  oranges, programs-director trip request) contained only facts Michael
  actually stated — the provenance guard had nothing to reject and nothing
  fabricated got through.

## The mark_resting event

```
14:47:44.327  speech_started (Aria's audio was actively playing)
14:47:46.032  USER: "You got it."          [3 words -> trusted, coherent_barge_in]
14:47:46.347  response_done
14:47:46.349  TOOL CALL: mark_resting
14:48:06.418  session_ended (reason: ui_end_call_button)
```

"You got it." was correctly transcribed, genuinely trusted speech — not a
transcription or trust-boundary failure. The model interpreted a
conversational wrap-up phrase as a request to go quiet. Root cause:
`mark_resting` has **no code-level gate at all**, unlike `request_staff_help`/
`request_transportation`/device tools, which all have a `turn_suspect`
check that can refuse regardless of the model's own judgment. The entire
protection on `mark_resting` is prompt wording, which the model overrode.

## Why did it become "listening but deaf"?

`resting` is purely cosmetic client-side UI state — it doesn't touch the
mic track, peer connection, or send any `session.update`. The WebRTC
connection reported no failure the entire session. But there is currently
**no signal that distinguishes "resident was silent" from "resident spoke
and it wasn't detected/relayed."** No mic audio-level logging, no
server-acknowledgment heartbeat. This needs new instrumentation before it
can be diagnosed with evidence rather than a guess.

## Phantom speech pattern

Every one of the 8 short (<=2-word) fragments that began during Aria's
audio overlap turned out wrong or unconfirmable (8 for 8). Every 3+-word
statement during overlap was genuinely real and correctly trusted (5 for
5). Speaker echo during playback overlap, not ambient-silence
hallucination, is the dominant mechanism this session.

## Architecture note (confirmed, not guessed)

The Realtime conversational model reasons directly over raw audio — it is
a native speech-to-speech model. `gpt-4o-transcribe` is a separate,
independent model given the same audio, run only to produce the on-screen/
saved transcript. The two are not guaranteed to agree. Clearest example
this session: the displayed transcript trailed off mid-sentence at
14:46:09, but Aria's spoken reply directly and correctly addressed what
Michael actually said — the conversational model understood more than the
transcript captured.

## Not yet applied (candidates for next round)

1. Code-level gate on `mark_resting`, same pattern as the Priority-1
   provenance guard — require the model's `reason` argument to match an
   explicit-dismissal allow-list before it's trusted.
2. Lightweight mic audio-level diagnostic logging, so a future "went deaf"
   period can be proven rather than inferred.
