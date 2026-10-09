# Audio-turn triage: Aria answers before the owner finishes (RQ-054, da-c2adf66033)

Scope: turn detection while talking. Not wake recognition, not RQ-050. Evidence is event-only
(no audio, no transcript content). One session was recorded: `rt_26qaw8y3_1791579663276`,
2026-10-09 21:01:04-21:01:42 UTC (16:01 CDT), Room 214 kiosk, woken by "Hey Aria".
Nothing live was changed.

## 1. Configuration in force (read, not guessed)
| Item | Value | Source |
|---|---|---|
| Capture device | EMEET OfficeCore Luna Plus, mono, Pulse source volume 100% / 0 dB, not muted | `pactl` |
| Browser mic constraints | echoCancellation, noiseSuppression, autoGainControl all true (browser default device "Default") | `realtimeConnection.js`, `mic_track_settings` event |
| Realtime VAD | `server_vad`, threshold 0.5, prefix_padding 300 ms, **silence_duration 1000 ms**, create_response true, **interrupt_response true** | `realtime_audio_config.py` |
| Input noise reduction | `far_field` | same |
| Wake listener | reads the same eMeet source raw (no echo cancellation), wake 0.05 / 1.5 unchanged | `aria-wake.env` |

## 2. What the events show
Joined with `scripts/turn_audit/turn_audit.py` (server events + the wake listener's `audio_level` summaries).
Seconds are from session start.

* **Capture level is not low.** Owner speech: peak -7.7 to -14 dBFS, mean -25 to -32 dBFS, noise floor -73 to -89 dBFS (about 55 dB signal-to-noise). A fan would show as a raised floor; the floor is -85 on average. More gain is not indicated.
* **The server ends a turn where the raw mic says the person stopped.** Server last-voiced vs raw last-voiced differs by 0.07 s, 0.23 s and 0.24 s across the three user turns. No evidence of clipped syllables or dropouts at turn end.
* **The assistant never speaks mid-turn on its own.** `response_created` follows `speech_stopped` by 10-20 ms every time. With `server_vad` the model only answers a turn the VAD closed, so this is VAD timing, not the model's social habit.
* **Turn 1 (8.44-10.96 s): 4 transcribed words.** The raw mic shows speech from about 8.2 to 9.9 s, a 0.6 s pause, then **raw speech again from 10.5 s (about 2.5 s long, mean -27.6 dBFS)**. That is 0.45 s *before* the server's `speech_stopped` (10.96 s) and before Aria's first audio (11.44 s), so it cannot be Aria's echo. The server did not register it: no `speech_started` until 16.91 s. Aria answered (11.44-16.9 s) over the rest of the sentence. This matches "you just cut me off".
* **Barge-in works once the server hears speech:** 16.91 s `speech_started` cleared Aria's audio immediately.
* **Turn 2** (10 words in an 8.5 s segment, 7.5 s of speech) was long and slow-paced but not cut.
* **End of call:** the first goodbye was refused as the grounding rule intends (`end_call` result), the second accepted; a farewell was logged without `end_call` once (RQ-041 counter). Cautious, not a proven defect.

## 3. Conclusion and what is not proven
* Proven: gain is not the problem; the 1000 ms hold was not exceeded by the owner's pause in raw capture (0.6 s); turn-end timing matches the raw mic.
* The cut-off in turn 1 is therefore not "VAD fired in a natural pause". The open question is why **raw speech that resumed 0.45 s before the commit was never treated as speech by the server**. Candidates, not yet separable: (a) Chrome echo cancellation / noise suppression / AGC attenuated the resumed words (the browser sends a processed track; the listener sees the raw one), (b) Realtime `far_field` noise reduction or VAD threshold 0.5 treated them as non-speech, (c) a small clock offset (about 0.25 s at most, from the 3-turn agreement) - too small to explain 0.45 s.
* Missing: the level of the processed track that is actually sent to OpenAI. Raw and server events cannot tell (a) from (b).

## 4. Recommendation: ONE reversible step, no setting change yet
Do **not** lengthen `silence_duration_ms`: the pause was shorter than the hold already, so a longer hold would only delay answers. Do not raise gain.
Enable the new event-only processed-track level telemetry, then repeat the owner test below.
* Change: `frontend/src/lib/micLevelTelemetry.js` (numbers per speech segment, `mic_level` events; no samples). Off unless the page is built with `REACT_APP_MIC_LEVEL_TELEMETRY=1`. Rollback: rebuild without it.
* Decision rule after the test: if `mic_level` shows the resumed words (about -27 dBFS) but the server heard nothing -> VAD/noise-reduction side (candidate: lower threshold, or `near_field`/off, one at a time). If `mic_level` is quiet there -> browser processing (candidate: `noiseSuppression:false` or `autoGainControl:false`, one at a time).
* Measurable pass: `turn_audit.py` reports no `raw_speech_resumed_s_before_commit` entries and no `during_assistant_playback` segment above -35 dBFS that is followed by a user barge-in more than 1 s later.

## 5. Owner test (about 5 minutes, needs a rebuild with the flag, which only Michael starts)
1. Fan ON, 1 m from the eMeet. Say "Hey Aria". Then say slowly with a half-second pause after each comma: "Oh, I was just checking on you, seeing how well you're doing, and wondering what you've been up to." Repeat three times.
2. Same, fan OFF.
3. Same, fan ON at 3 m.
4. Note which runs Aria spoke before the end of the sentence (a tally is enough).
Then run `backend/.venv/bin/python scripts/turn_audit/turn_audit.py <session_id>` for each session id (session ids are in the Resident Record) and compare with `mic_level` events. No audio is recorded; no live setting is changed by this test.

## 6. Limits
One session; timing alignment between the listener clock and server events is about 0.25 s; the 0.45 s lead is larger but not proof; the raw source includes Aria's own voice during playback, so playback-time segments are ambiguous; I do not have the owner's wording, only counts.
