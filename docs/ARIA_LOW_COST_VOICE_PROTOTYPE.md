# Aria low-cost voice (aria-low-cost-streaming-voice-001, PR #192)

Status: owner-approved for Room 214 (2026-10-17: "load", with a switch to Realtime). No Realtime model on this path.
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
- Barge-in: while she is audible, sound over her voice only lowers it (to 30%); words - from the early transcription
  at the speaker's first pause, or at turn end - stop her and cancel queued speech. No words (her own voice from
  the room speaker, noise) and she carries on at full volume and nothing is answered. Before she is audible, speech
  stops her at once. (Room 214 2026-10-17 rt_sf8ft3v6: 7 of 9 interruptions had no words. Same idea as LiveKit's
  false-interruption resume and Pipecat's minimum-words turn start.) A new turn arriving while a reply is still
  being written replaces that reply. Late chunks of cancelled speech are discarded. Only sentences played to their end (read off the audio clock) remain in the conversation;
  queued, failed or cut-off speech does not.
- Playback: through a local WebRTC loopback into the page's audio element so Chrome's AEC removes her voice; nothing
  plays until that loopback is connected (else direct, recorded as `output: direct`). After the player runs dry it
  holds 200 ms (or the sentence's end) before resuming - one rebuffer instead of a stutter; no audio is dropped.
- Speech failures: `/speak` answers 502 when the provider gives no audio (never an empty 200); the page records
  each failed / empty / unreachable / interrupted sentence (`cascade_speech_failed`).
- Receipts (metadata only, `realtime_diagnostics`): `cascade_playback` per reply (first audio, underruns, sentence
  gaps, queue depth, buffered ms, heard vs partial, outcome) and `cascade_barge_in` (words in the interrupting turn
  - 0 points to echo or noise).
- Measurement (Room 214 only, owner-approved 2026-10-17, off by default): `ARIA_WAKE_DIAG_KIOSKS=<kiosk ids>` in
  `aria-wake.env` + `ctl.sh rebuild` turns on, for those kiosks only, `mic_level` (processed-track level per speech
  segment, `micLevelTelemetry.js`) and `cascade_vad_diag` from the voice service (`Diag`): per level segment of the
  audio Silero read, its levels, VAD-flagged 100 ms frames, whether a turn started, and `no_speech_detected` when
  there was energy but no detected speech; every 30 s, frame arrival (`wall_s`/`audio_s`/gaps). Numbers only,
  at most 30 per minute. sherpa-onnx does not expose Silero's probability, so flagged frames are the score.
  `mic_diagnostics_enabled` marks a measured session. Off: remove the line, rebuild.
- Greeting: `_caos.greeting_line`, spoken with no reasoning call; its audio is cached after first use (only the
  greeting is ever cached — conversation audio is never stored).
- Pronunciation: `backend/aria_voice_lexicon.json` (KAY-oss Care), applied only to text sent to speech.

## Voice
The kiosk's existing voice picker chooses it (marin and cedar added); every voice runs on one speech model,
`ARIA_VOICE_TTS_MODEL` (gpt-4o-mini-tts), so all cost the same. In low-cost mode the picker's preview plays through
the same speech path. Audition history: tts-1 sage was slow to first audio; owner chose nova (2026-10-17), the default.

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

## Choosing the transport (per room)
- `ARIA_VOICE_CASCADE=1` makes the low-cost voice available; `ARIA_VOICE_DEFAULT_TRANSPORT=cascade` makes it the
  rooms' default. Each kiosk's setting and voice live on its Kiosk record (`routes/aria_voice_prefs.py`,
  `GET /api/aria-voice/config`, `POST /api/aria-voice/kiosks/{id}/prefs`, changes logged): the kiosk's
  "Low-cost / Realtime" button and voice picker change the room from any screen showing that kiosk.
  `?aria_voice=<mode>` overrides for one test page.
- Live rooms: every provider call receipted, never blocked or capped (as Realtime); a session stays valid while in
  use (30 min idle). Paid tests (`CAOSCARE_PAID_TEST_BUDGET_ID`): bounded sessions reserved against the owner's
  budget, fail closed.
- Room node: `aria-voice.service` (installed by `room-node/aria_wake/ctl.sh install-voice`, VAD model in
  `room-node/aria_voice/model/`). Future (owner): residents choose their experience and see the cost difference.

## Audition
Prototype backend :8097 on a DB snapshot (`caoscare_aria_voice_audition`, escalations off), page :3005, voice
service :8794 — live :8092/:3002, wake, kiosk untouched. Open
`http://localhost:3005/kiosk/<kiosk>?aria_voice=cascade` and tap to talk; the live wake
listener drives the live page, so the audition does not use "Hey Aria" until the owner approves loading.
