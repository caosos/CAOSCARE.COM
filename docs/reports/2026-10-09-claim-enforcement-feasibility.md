# RQ-050: can a false Aria claim be stopped before it is heard? (feasibility)

Offline only. No provider was called. Event names below were re-read from the OpenAI Realtime reference on 2026-10-09 (server-events and client-events pages).

## Confirmed provider facts
- `response.output_audio_transcript.delta` (fields `delta`, `response_id`, `item_id`) and `.done` (full `transcript`; also emitted when a response is interrupted, incomplete or cancelled).
- Client `response.cancel` (optional `response_id`) stops generation; `response.done` then has status `cancelled`, reason `client_cancelled`.
- Client `output_audio_buffer.clear` (WebRTC/SIP only) cuts off the current audio; the docs say it "should be preceded by a `response.cancel`". The server then emits `output_audio_buffer.cleared`, which the handler already consumes.
- `response.create` accepts `response.instructions`.

## (a) Can an action-success sentence be gated BEFORE it is heard? No (not for arbitrary sentences)
Audio and transcript are produced together and played as they arrive. The only way to inspect a sentence before the resident hears it is to hold the audio until the whole sentence (or response) is complete. Real timing from `realtime_diagnostics` (10,623 events, 838 responses with audio):

| measure | p10 | p50 | p90 |
|---|---|---|---|
| response.created -> first audio (ms) | 204 | 410 | 647 |
| audio playback length per response (ms) | 1106 | 4640 | 9920 |
| assistant words per transcript | | 17 | 38 |

Holding a whole response adds its full playback length (median about 4.6 s, p90 about 9.9 s) of silence before every answer, and the WebRTC audio path has no client-side hold: the browser plays the remote track as it arrives. Doing it would need an audio re-render path (text-to-speech after our check) replacing the realtime voice. That is a change of architecture, not a safeguard, and it breaks conversation feel. Not done.

## (b)(1) What is feasible: a fail-closed interrupter (built, default OFF)
`frontend/src/lib/claimInterrupter.js`, wired in `realtimeMessageHandler.js`. Mode comes from `REACT_APP_CLAIM_INTERRUPTER`: `off` (default, inert), `shadow` (logs `claim_interrupter_would_cut` with `ms_since_response_created`, sends nothing), `on`.
Behaviour (on): accumulate transcript deltas per response; once a COMPLETE sentence claims an action, a stated weather fact or a live lookup, and no ok tool result in the same resident turn backs it, send `response.cancel` (that response), `output_audio_buffer.clear`, then one corrective `response.create` whose instructions state only that nothing has been sent and to offer a staff request. Once per resident turn; the corrective response is never itself interrupted.
Guards: no cut while a tool call is in flight (result arriving after the sentence began), after an emergency or live-line tool (`call_for_help`, `request_live_staff`, `end_call`, `end_conversation`, `mark_resting`), for questions or conditionals ("should I tell the nurse?", "if you want"), or when a matching ok result exists (`get_weather`, live `research_topic`, any ok action tool).

### Leakage that cannot be avoided (stated honestly)
- Words already played before the sentence ends are heard. Detection waits for the sentence terminator (so a trailing "if you like" is seen), so the cut lands at the end of the claim sentence plus transcript/round-trip lag. Transcript deltas are not logged today, so the exact delta-to-playback lead cannot be measured from history; deltas normally run ahead of playback, so the cut is expected to land close to the end of the offending sentence (typically 1 to 3 s of speech for a 17-word median answer), but that is NOT measured. Shadow mode produces the measurement (`ms_since_response_created` per would-cut).
- If the cancelled response was about to emit a tool call, that call is lost. The corrective turn then tells the truth (nothing sent) and offers to file a request, so the failure is honest.
- Regex detection can miss a paraphrased claim and can mis-fire; it is a floor, not a proof.

## (b)(2) Structural alternative (built, mode "on" only)
`verifiedConfirmationEvent()`: after an ok action tool result, the dispatcher sends `response.create` with instructions that carry the verified `result.message` ("say only this"), instead of a bare `response.create`. It removes the model's room to improvise "I told the nurse" beyond the tool result. Not applied to end_call / mark_resting branches (unchanged) or failed results. Tool-description wording against pre-tool narration was already added in RQ-045.

## Tests
`frontend/src/lib/__tests__/claimInterrupter.test.js` (11): false claim cancel+clear+corrective once; sentence terminator wait; same sentence after ok result untouched; tool in flight; failed result does not back a claim; two claims one corrective and corrective not re-interrupted; emergency path never interrupted; questions/conditionals; weather and lookup claims; re-arm per turn, shadow, off.

## What this does not prove
No live model behaviour was observed (no paid calls). Whether `output_audio_buffer.clear` after `response.cancel` is clean in the browser, and the real audio leaked, need a physical/shadow run.
