/**
 * Regression test, Room 214 session rt_wpngzbuw_1790215179553 (2026-09-23):
 * "I'm going to bed" -> mark_resting refused by the grounding guard (asks
 * for confirmation), but the handler still put Aria to rest and never sent
 * response.create, so she went silent. A refusal must be spoken; only a
 * granted rest may disable auto-response.
 */
jest.mock("../api", () => ({ API: "http://localhost:8000/api" }));
jest.mock("../realtimeDiagnostics", () => ({
  logRealtimeEvent: jest.fn(), transcriptionConfidence: () => null, LOW_CONFIDENCE_THRESHOLD: 0.5,
}));
jest.mock("../realtimeDeviceTools", () => ({ executeDeviceTool: jest.fn() }));
jest.mock("../realtimeOperationsTools", () => ({ executeOperationsTool: jest.fn(async () => null) }));
jest.mock("../realtimeDisplayTools", () => ({ executeDisplayTool: jest.fn(async () => null) }));
jest.mock("../realtimeCareControl", () => ({ executeCareTool: jest.fn(async () => null), ringLiveLineOnSilence: jest.fn() }));
import { createRealtimeHandlers } from "../realtimeMessageHandler";
import { executeDeviceTool } from "../realtimeDeviceTools";

function harness() {
  const sent = [];
  const setResting = jest.fn();
  const startGenRef = { current: 1 };
  const h = createRealtimeHandlers({
    myGen: 1, startGenRef, sessionIdRef: { current: "rt_test" }, ctxRef: { current: { room: "214" } },
    caos: { turn_detection: { type: "server_vad" } }, send: (m) => sent.push(m), stop: jest.fn(), onEndCall: jest.fn(),
    turnSuspectRef: { current: false }, assistantSpeakingRef: { current: false }, restingRef: { current: false },
    greetingCreateResponseOffRef: { current: false },
    setStatus: jest.fn(), setResting, setTranscript: jest.fn(), setError: jest.fn(),
    startAwaitingAnswerTimer: jest.fn(), onSpeechEvent: jest.fn(), onFirstSpeechStarted: jest.fn(),
  });
  return { h, sent, setResting };
}

test("refused mark_resting is spoken (response.create), not a silent rest", async () => {
  executeDeviceTool.mockResolvedValueOnce({ ok: false, message: "Just to make sure — would you like me to go quiet for a bit?" });
  const { h, sent, setResting } = harness();
  await h.handleFunctionCall({ call_id: "c1", name: "mark_resting", arguments: "{}" });
  expect(setResting).not.toHaveBeenCalledWith(true);
  expect(sent.map((m) => m.type)).toEqual(["conversation.item.create", "response.create"]);
});

test("granted mark_resting still rests and turns auto-response off", async () => {
  executeDeviceTool.mockResolvedValueOnce({ ok: true, message: "resting" });
  const { h, sent, setResting } = harness();
  await h.handleFunctionCall({ call_id: "c2", name: "mark_resting", arguments: "{}" });
  expect(setResting).toHaveBeenCalledWith(true);
  expect(sent.map((m) => m.type)).toEqual(["conversation.item.create", "session.update"]);
  expect(sent[1].session.audio.input.turn_detection.create_response).toBe(false);
});
