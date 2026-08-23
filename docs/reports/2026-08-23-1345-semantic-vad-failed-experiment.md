# semantic_vad + eagerness "low" — failed experiment, reverted

**Session:** Chauncey / Room 304, `rt_pc5lblon_1787453286910`
**Status:** Reverted. `DEFAULT_VAD` is back to `server_vad`.

## What was tried

`backend/routes/realtime.py`'s `DEFAULT_VAD` was changed from `server_vad`
(threshold 0.5, prefix_padding_ms 300, silence_duration_ms 1000) to
`semantic_vad` with `eagerness: "low"` — a real, current OpenAI Realtime
API mechanism (verified against the official docs before applying, not
guessed), intended to let a resident finish a thought without a fixed
silence timer chopping it into separate turns. Applied with Michael's
explicit approval, backend restarted, confirmed live via a fresh session
mint before testing.

## Result: failed

Live test on Chauncey/Room 304. Michael's words: "it doesn't work at
all... the recording times out or stops listening while appearing to be
listening."

Forensic reconstruction from `db.realtime_diagnostics` confirmed this
precisely: after 3 real exchanges (~53 seconds), the system produced
**zero `speech_started` events for a full 38 seconds** while the WebRTC
connection remained healthy throughout (`pc_connection_state: connected`,
no failure/error event) — a genuine turn-detection failure, not a network
one. Michael manually ended the call (`session_ended` reason:
`ui_end_call_button`).

The prior `server_vad` session ran ~7 continuous minutes with no gap
anywhere near this size. One turn ("I broke it.") also came from a
6.3-second speech segment that collapsed to just 3 transcribed words,
consistent with the same detection problem — transcription itself was
accurate this test (no phantom garbage), so this wasn't an accuracy issue.

Aria's response quality also showed real reasoning mismatches unrelated to
VAD (e.g. "I broke it." → "I'm glad. It's good to have this connection.")
— flagged separately, not investigated this round.

The queued provenance-guard / `mark_resting` test items were never
reached — the dead zone ended the call before the test script got there.

## What changed (the revert)

`DEFAULT_VAD` restored to `server_vad` with the exact prior parameters,
plus `interrupt_response: true` added explicitly (Michael-directed, valid
alongside `server_vad` too, wasn't in the original config). Backend
restarted, confirmed live via a fresh session mint that `server_vad` with
the exact prior parameters is actually being served again.

## Important follow-up

A same-day post-revert test showed `server_vad` is *also* not reliably
good — real speech came through as one/two-word fragments and Aria talked
over natural thinking pauses. See
`2026-08-23-1448-room304-morning-forensics.md` for the full breakdown.
Both VAD modes have now been tested live and both have real, distinct
failure modes; neither is currently a clean "known good" baseline.
