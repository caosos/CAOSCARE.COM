# Aria low-cost voice — prototype (aria-low-cost-streaming-voice-001, draft PR #192)

Status: side-by-side audition only. Not the Room 214 default. No Realtime model. Owner decides by listening.
Owner rule: Michael's genuine personal use ≤ $10/month (≤ $15 acceptable for clearly better, hard ceiling $20).

## One Aria, another transport
Aria's behaviour lives in `frontend/src/lib/realtimeMessageHandler.js` and its tool modules (tools, grounding,
goodbye/end-call, memory ingest, receipts). It reaches the provider through one seam in `realtimeConnection.js`
(`send` / `onMessage` on a data channel). The prototype replaces only what stands behind that seam. Instructions,
tools, opening and context come from the same builder as the Realtime room session (`realtime_resident_session._mint`).
The old Turn mode (`/api/ai/chat`, its own `CAOS_SYSTEM_PROMPT`, a fixed 14 s listen window, no tools) is not used.

```
room page: handler + tools (unchanged) ◀── Realtime event subset ──▶ cascadeTransport.js
   mic (browser AEC) ─PCM─▶ room-node/aria_voice  (localhost :8794, Silero VAD: pause, turn end, barge-in)
                            backend routes/aria_voice.py  (key, receipts, budget; models/voice = configuration)
                              /transcribe  ARIA_VOICE_STT_MODEL  (gpt-4o-mini-transcribe)   speech_transcription
                              /respond     ARIA_VOICE_TEXT_MODEL (gpt-4o-mini, streamed, 34 tools)  room purpose
                              /speak       session voice, streamed PCM 24 kHz                speech_generation
```
Swapping the text provider means a new `_stream()` in `routes/aria_voice.py`; nothing else changes.

## Turn taking
- Turn end: Silero VAD with `silence_duration_ms` from `realtime_audio_config.DEFAULT_VAD` (same as Realtime).
- Early transcription at a 400 ms pause; reused if the turn ends there, discarded if Michael carries on.
- Reply text streams; each finished sentence (the first clause at its comma) is voiced at once, played in order.
- Barge-in: speech over Aria stops playback immediately and cancels queued speech; only sentences that reached
  the speaker remain in the conversation.
- Greeting: `_caos.greeting_line`, spoken with no reasoning call; its audio is cached after first use (only the
  greeting is ever cached — conversation audio is never stored).
- Pronunciation: `backend/aria_voice_lexicon.json` (KAY-oss Care), applied only to text sent to speech.

## Audition voices (at most three)
`tts-1:sage` (Aria 2026-04-19/20), `tts-1:shimmer` (04-21, just before Realtime), `gpt-4o-mini-tts:marin` (today's
voice). Chosen per session with `&aria_voice_tts=<key>`; default `ARIA_VOICE_TTS`.

## Accounting
Every provider call is receipted in `caoscare_paid_api_ledger` with purpose, session, model, provider ids, usage and
estimate (pricing version). tts-1 reports no usage; its cost is billed per character and settles as known.
Audition sessions reserve their worst case against the owner's test budget (fail closed). Page diagnostics for a
cascade session never add a second receipt.

## Measured (EliteDesk; history)
- Local voices were tried first and rejected: Kokoro 0.33–1.0x real time (cannot stream here); Piper fast but
  "robotic" (owner).
- Real calls (2026-10-17): speech end → Aria audio 2.4–4.7 s before early transcription, 1.55–1.65 s after
  (tool turns ~2.2 s, local voice). Per response ~$0.0012 (15k-token prompt, 97–99% cached).
- Michael's genuine use (Room 214 sessions 10-13…10-17, classified): ~9.7 min/day (12.7 with unknowns); the rest
  of that week was testing.

## Audition
Prototype backend :8097 on a DB snapshot (`caoscare_aria_voice_audition`, escalations off), page :3005, voice
service :8794 — live :8092/:3002, wake, kiosk untouched. Open
`http://localhost:3005/kiosk/<kiosk>?aria_voice=cascade&aria_voice_tts=<voice>` and tap to talk; the live wake
listener drives the live page, so the audition does not use "Hey Aria" until the owner approves loading.
