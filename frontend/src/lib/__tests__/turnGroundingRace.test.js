/**
 * Regression test for a real live incident, 2026-08-30, session
 * rt_2p0zhj1l_1788116179150: "I need you to go away." and "End the call."
 * both fired end_call, but both were rejected by the backend's
 * ENDING_PHRASES grounding guard - db.realtime_diagnostics showed
 * response.function_call_arguments.done landing BEFORE conversation.item.
 * input_audio_transcription.completed for the very turn that triggered
 * it, so ctx.last_user_text was empty/stale at grounding-check time. This
 * tests the fix directly (createTurnGroundingTracker), independent of any
 * network/WebRTC timing.
 */
import { createTurnGroundingTracker } from "../realtimeTurnGrounding";

test("real incident: waitForGroundedTurn resolves with the racing turn's own text, not stale/empty", async () => {
  const t = createTurnGroundingTracker();
  t.onSpeechStopped(); // "I need you to go away." ends
  // Simulate the tool call racing ahead - transcription lands 150ms later,
  // matching the real observed 137-184ms lag.
  setTimeout(() => {
    t.onTranscriptionCompleted({ suspect: false, reason: "no_overlap" }, "I need you to go away.");
  }, 150);
  const cls = await t.waitForGroundedTurn();
  expect(cls.text).toBe("I need you to go away.");
});

test("no pending transcript: resolves immediately with whatever is already known", async () => {
  const t = createTurnGroundingTracker();
  t.onTranscriptionCompleted({ suspect: false, reason: "no_overlap" }, "Turn the TV on.");
  const start = Date.now();
  const cls = await t.waitForGroundedTurn();
  expect(cls.text).toBe("Turn the TV on.");
  expect(Date.now() - start).toBeLessThan(50); // no wait incurred
});

test("transcript never arrives: falls back to prior known turn after the wait ceiling, doesn't hang forever", async () => {
  const t = createTurnGroundingTracker();
  t.onTranscriptionCompleted({ suspect: false, reason: "no_overlap" }, "earlier turn");
  t.onSpeechStopped(); // a new segment starts, but its transcript never lands
  const cls = await t.waitForGroundedTurn();
  expect(cls.text).toBe("earlier turn"); // stale, but NOT empty/hung - honest best-known state
}, 2000);

test("sequential turns: second call() correctly waits for its OWN transcript, not the first's", async () => {
  const t = createTurnGroundingTracker();
  t.onSpeechStopped();
  setTimeout(() => t.onTranscriptionCompleted({ suspect: false, reason: "no_overlap" }, "first"), 50);
  const first = await t.waitForGroundedTurn();
  expect(first.text).toBe("first");

  t.onSpeechStopped();
  setTimeout(() => t.onTranscriptionCompleted({ suspect: false, reason: "no_overlap" }, "End the call."), 150);
  const second = await t.waitForGroundedTurn();
  expect(second.text).toBe("End the call.");
});
