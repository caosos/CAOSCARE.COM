# Adaptive conversation tempo — 2026-08-29

## Agent / tool
ChatGPT-Aria via GitHub connector.

## Branch / ref
`feature/adaptive-conversation-tempo`, based on `main` at `307a011`.

## Michael's requirement
The Care app voice should feel more like a real full-duplex conversation: **"match the tempo"**, allow the speaker to finish, follow starts/stops/restarts and thinking-out-loud, and still yield immediately to a real interruption.

## Evidence checked before changing code
- Current repo uses OpenAI Realtime over WebRTC with `server_vad`.
- The known-good baseline was `server_vad`; the prior `semantic_vad` + low-eagerness experiment produced a real ~38-second detection dead zone and was reverted. This build deliberately does **not** return to that path.
- Existing Room 304/408 evidence established that coherent barge-in is real speech and must remain allowed; overlap alone is not an echo verdict.
- Current OpenAI Realtime documentation confirms VAD can remain enabled while `create_response` is disabled, allowing the client to decide when to send `response.create`. `input_audio_buffer.speech_started` / `speech_stopped` also include the speech item's `item_id`.

## What changed
### 1. New adaptive floor controller
New `frontend/src/lib/realtimeConversationTempo.js`.

The controller keeps server VAD as the speech detector/chunker but owns **when Aria takes the floor**:
- `create_response` remains off for the whole call.
- A normal completed speech segment starts a short grace timer before `response.create`.
- If the person starts speaking again before the timer fires, the pending reply is canceled and the grace window grows for the next turn.
- If the person consistently yields the floor, the grace window tightens gradually.
- Operator profile starts tighter/faster; resident profile starts with more room.
- Exact Realtime `item_id` values bind delayed/suspect decisions to the correct speech turn so an older echo classification cannot cancel a newer real turn.
- A turn that started during Aria playback waits for the existing trust classifier before any reply: suspect echo is suppressed; a coherent real barge-in is allowed through.
- A separately-created greeting/tool response cancels any stale delayed response.
- New diagnostics: `tempo_response_scheduled`, `tempo_response_create`, `tempo_user_resumed`, `tempo_waiting_for_overlap_classification`, `tempo_suspect_turn_suppressed`.

### 2. Conversation-rhythm instruction
The Realtime session now appends a small explicit rhythm rule: match the person's conversational tempo; let them finish; do not treat a filler, restart, half-sentence, short pause, or quick change of direction as automatically complete; tighten replies for a fast speaker; leave more room for a slower speaker; yield immediately to interruption; do not fill every silence.

This is applied in `realtimeSessionUpdate.js` while preserving the backend-provided authoritative prompt.

### 3. VAD remains server_vad, but its silence boundary is quicker
`backend/routes/realtime_audio_config.py` changes `silence_duration_ms` from `1000` to `700` ms.

Reason: the new client grace period now handles conversational hesitation after VAD has chunked a segment. Keeping 1000 ms *plus* an adaptive grace would make every clean turn slower. The 700 ms VAD boundary plus the initial adaptive grace produces an effective initial floor wait of roughly:
- operator: 700 + 250 = 950 ms
- resident: 700 + 450 = 1150 ms

If the speaker resumes during that grace window, Aria does not answer and the controller learns to wait longer next time.

### 4. Greeting behavior updated
The forced initial greeting is still an explicit `response.create`, but automatic VAD responses are no longer re-enabled after greeting playback. `interrupt_response` remains enabled, so real barge-in still cuts Aria off.

## Tests added
New `frontend/src/lib/realtimeConversationTempo.test.js` covers:
1. normal operator floor timing;
2. resumed thought cancels the pending reply and expands the grace window;
3. suspect overlap does not get a reply;
4. coherent barge-in does get a reply;
5. stale echo classification cannot cancel a newer real turn;
6. rhythm instructions preserve the backend base prompt.

These tests are committed but were **not executed in this connector-only environment** because the repository/runtime is not locally mounted and the repo has no GitHub Actions workflow. Live WebRTC acceptance is also still required.

## Production-file line counts
- `backend/routes/realtime_audio_config.py`: 27 lines.
- `frontend/src/lib/realtimeConversationTempo.js`: 109 lines.
- `frontend/src/lib/realtimeMessageHandler.js`: 294 lines.
- `frontend/src/lib/realtimeSessionUpdate.js`: 63 lines.
- `frontend/src/lib/useRealtimeVoice.js`: 250 lines.

All modified/created production files remain under the repo's 300-line hard cap.

## Not changed
- No production deployment.
- No merge to `main` yet.
- No semantic VAD.
- No change to browser AEC/noise-suppression capture constraints.
- No widening of the existing trust classifier.
- No device-control, memory, facility, clinical, or staff workflow changes.

## Live acceptance target
A short real conversation should deliberately include:
1. a quick clean question — Aria should answer without a sluggish pause;
2. a sentence with a deliberate ~0.8-second thinking pause, then continuation — Aria should hold the floor and let the speaker continue;
3. several stop/start thought fragments — the grace window should adapt rather than repeatedly cutting in;
4. a real interruption while Aria is speaking — Aria should stop and follow the interruption;
5. normal silence after a genuinely finished thought — Aria should respond rather than hang;
6. one greeting/echo-prone opening — no second greeting should be triggered by suspected playback echo.

Diagnostics from that session should show whether `tempo_user_resumed` fires when the person continues and whether the learned `grace_ms` moves in the expected direction.

## Blocked / pending
- Run the new frontend unit tests on the EliteDesk or another repo checkout.
- Run the real WebRTC acceptance sequence above.
- If accepted, merge the branch; production deployment remains a separate explicit action.
- `docs/PROJECT_STATE.md` still needs the matching dated summary appended by a tool/runtime capable of append/patch. The current GitHub connector only exposes full-file replacement for existing files, and `PROJECT_STATE.md` is too large to safely reconstruct from truncated reads in this session.
