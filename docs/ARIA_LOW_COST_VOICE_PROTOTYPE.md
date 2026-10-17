# Aria low-cost streaming voice — prototype blueprint (aria-low-cost-streaming-voice-001)

Status: PROTOTYPE, side-by-side audition only. Not the Room 214 default. No Realtime model is used.
Owner budget: $1 total paid testing (ledger budget, fail closed). Target: Michael personal use <= $10/month.

## Principle: replace the transport, not Aria
Aria's behaviour lives in `frontend/src/lib/realtimeMessageHandler.js` (+ tool modules): tool dispatch, turn
grounding, goodbye handling, receipts, memory ingest. It talks to the provider through exactly one seam in
`realtimeConnection.js`: `send(clientEvent)` / `onMessage(serverEvent)` on the data channel, plus one audio element.
The prototype keeps all of that and swaps only what is behind the seam. Instructions, tools, opening and context
come from the same builder as the Realtime room session — one source of truth, no forked prompt or tool list.

```
browser room page (unchanged handler + tools)
  mic (getUserMedia, browser AEC) ──PCM16──▶ ┐
  speaker  ◀──PCM16 (Aria audio)──────────── │  cascade transport (WebSocket, Realtime event subset)
  send()/onMessage() ◀──Realtime events────▶ ┘
                                               room-node/aria_voice (EliteDesk, local)
                                                 Silero VAD + endpointing (same silence_duration_ms)
                                                 conversation items (Realtime-style state)
                                                 Piper TTS, sentence streaming, pronunciation lexicon
                                                     │ (no provider key on the room node)
                                                     ▼
                                               backend /api/aria-voice/*  (key, receipts, budget)
                                                 transcribe: gpt-4o-mini-transcribe  purpose speech_transcription
                                                 respond:    gpt-4o-mini stream+tools purpose room214_conversation
```

## Event contract (subset the handler already uses)
Server → browser: session.created, session.updated, input_audio_buffer.speech_started / speech_stopped,
conversation.item.input_audio_transcription.completed, response.created, response.output_audio_transcript.delta /
.done, response.function_call_arguments.done, output_audio_buffer.started / stopped / cleared, response.done, error.
Browser → server: session.update, conversation.item.create (message, function_call_output), response.create,
response.cancel, output_audio_buffer.clear.

## Behaviour targets
- Turn end: Silero VAD, `silence_duration_ms` read from `realtime_audio_config.DEFAULT_VAD` (pauses like today).
- Barge-in: VAD runs during playback; speech_started → stop playback within one audio frame, emit
  output_audio_buffer.cleared; the handler's existing cancel logic runs unchanged.
- Streaming: text is streamed from the model; each finished sentence is synthesized and played while the next is
  generated. Tool calls are executed by the existing browser tool modules.
- Pronunciation: one lexicon (`room-node/aria_voice/lexicon`) applied before TTS; "CAOSCare"/"CAOS Care" →
  "KAY-oss Care".
- Receipts: every provider call goes through the backend helpers and `paid_api_ledger` (no key on the room node).

## Measured (EliteDesk 800 G4 mini, Ryzen 5 PRO 2400GE, 4C/8T, AVX2, no fast int8), 24 real Aria sentences
| Local TTS | speed vs real time | first sentence ready (median) |
|---|---|---|
| Kokoro-82M int8 (sherpa 1.13.8), 4 threads | 0.33x | 7.7 s |
| Kokoro-82M fp32, 4 threads | 1.02x | 2.5 s |
| Kokoro-82M fp32, 8 threads | 0.85x | 2.9 s |
| Piper en_US-lessac-medium, 4 threads | 12x | 0.21 s |
Kokoro cannot stream on this CPU (no headroom for wake/VAD). Piper is the prototype voice; the TTS sits behind one
interface so Kokoro (faster host) or a paid voice can replace it.

## Measured, room-node half (same box)
- First audio per sentence (Piper, 4 threads, service warm): 0.11–0.29 s.
- Barge-in: after `stop`, no frame of the interrupted reply is sent (generation-tagged frames, synthesis aborted).
- Turn end on a recorded room clip: ~1.1 s after speech ends (silence_ms 1000 from DEFAULT_VAD).

## Cost projection (before audition receipts replace it)
Michael's real Room 214 profile on Realtime mini since 2026-10-15 23:44Z (realtime_diagnostics): 24 sessions,
49.4 min, 4.86 responses/min, 3.34 user turns/min; measured mini cost $0.031/min.
Cascade per response: ~15.2k input tokens (measured Realtime prompt size: half tools, half instructions), ~79%
cached → ~$0.0014 at gpt-4o-mini prices; transcription ~3 user turns/min of short speech → ~$0.001/min.
Projection ≈ $0.008/min (≈4x below mini). At ~33 min/day ≈ $8/month; at 48 min/day ≈ $11.5/month — the main
lever is the tool-schema half of the prompt. The audition's ledger receipts are the measurement of record.

## Audition (side-by-side, nothing live touched)
- Prototype backend 127.0.0.1:8097 on a DB snapshot (`caoscare_aria_voice_audition`), escalations off,
  ARIA_VOICE_CASCADE=1, owner budget `aria-low-cost-voice-001` ($1 cap). Receipts go to the real ledger.
- Prototype page :3005 (`serve_built.js` with its own build dir); voice service :8794.
- Open `http://localhost:3005/kiosk/<kiosk>?aria_voice=cascade` and tap to talk. The live wake listener drives
  the live page, so the audition does not use "Hey Aria"; wiring wake to the cascade waits for acceptance.
