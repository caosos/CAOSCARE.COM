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
