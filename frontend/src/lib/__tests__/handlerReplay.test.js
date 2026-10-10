/**
 * Test-reality gap 6: a recorded-shape server-event stream (sanitized, synthetic text) replayed
 * through the REAL message handler: resident speaks, the transcript completes, the model calls a
 * tool, the result goes back, the model is asked to speak. Asserts dispatch order, the grounding
 * text the tool receives (the resident's own words), and the response.create timing.
 */
const mockLog = jest.fn();
jest.mock("../api", () => ({ API: "http://api.test/api" }));
jest.mock("../realtimeDiagnostics", () => ({
  logRealtimeEvent: (...a) => mockLog(...a), transcriptionConfidence: () => null, LOW_CONFIDENCE_THRESHOLD: 0.5,
}));
jest.mock("../realtimeDeviceTools", () => ({ executeDeviceTool: jest.fn() }));
jest.mock("../realtimeOperationsTools", () => ({ executeOperationsTool: jest.fn(async () => null) }));
jest.mock("../realtimeDisplayTools", () => ({ executeDisplayTool: jest.fn(async () => null) }));
jest.mock("../realtimeCareControl", () => ({ executeCareTool: jest.fn(async () => null), ringLiveLineOnSilence: jest.fn() }));
import { createRealtimeHandlers } from "../realtimeMessageHandler";
import { executeDeviceTool } from "../realtimeDeviceTools";

const flush = () => new Promise((r) => setTimeout(r, 30));
const feed = (on, o) => on({ data: JSON.stringify(o) });

function setup() {
  const sent = [];
  const startGenRef = { current: 1 };
  const h = createRealtimeHandlers({
    myGen: 1, startGenRef, sessionIdRef: { current: "rt_replay" }, ctxRef: { current: { room: "214", resident_id: "r1" } },
    caos: { turn_detection: { type: "server_vad" } }, send: (m) => sent.push(m), stop: jest.fn(), onEndCall: jest.fn(),
    turnSuspectRef: { current: false }, assistantSpeakingRef: { current: false }, restingRef: { current: false },
    greetingCreateResponseOffRef: { current: false }, setStatus: jest.fn(), setResting: jest.fn(),
    setTranscript: jest.fn(), setError: jest.fn(), startAwaitingAnswerTimer: jest.fn(), onSpeechEvent: jest.fn(), onFirstSpeechStarted: jest.fn(),
  });
  return { on: h.onMessage, sent };
}

beforeEach(() => { mockLog.mockClear(); global.fetch = jest.fn(async () => ({ ok: true, json: async () => ({}) })); });

test("transcript -> tool call -> result -> response.create, in that order, grounded on the resident's words", async () => {
  executeDeviceTool.mockImplementationOnce(async ({ ctx }) => ({ ok: true, message: `done (heard: ${ctx.last_user_text})` }));
  const { on, sent } = setup();
  feed(on, { type: "input_audio_buffer.speech_started" });
  feed(on, { type: "input_audio_buffer.speech_stopped" });
  feed(on, { type: "conversation.item.input_audio_transcription.completed", item_id: "i1", transcript: "Please turn the light on." });
  feed(on, { type: "response.function_call_arguments.done", call_id: "c1", name: "toggle_light", arguments: '{"state":"on"}' });
  await flush();
  expect(executeDeviceTool).toHaveBeenCalledTimes(1);
  expect(executeDeviceTool.mock.calls[0][0].args).toEqual({ state: "on" });
  expect(executeDeviceTool.mock.calls[0][0].ctx.last_user_text).toBe("Please turn the light on.");
  // sent: the tool output first, then exactly one request to speak
  expect(sent.map((m) => m.type)).toEqual(["conversation.item.create", "response.create"]);
  expect(sent[0].item).toMatchObject({ type: "function_call_output", call_id: "c1" });
  expect(JSON.parse(sent[0].item.output).message).toContain("Please turn the light on.");
  // diagnostics order
  const t = mockLog.mock.calls.map((c) => c[1]);
  expect(t.indexOf("user_transcript")).toBeLessThan(t.indexOf("tool_call"));
  expect(t.indexOf("tool_call")).toBeLessThan(t.indexOf("tool_result"));
});

test("a tool call arriving BEFORE its transcript still waits for the resident's words", async () => {
  executeDeviceTool.mockImplementationOnce(async ({ ctx }) => ({ ok: true, message: ctx.last_user_text }));
  const { on, sent } = setup();
  feed(on, { type: "input_audio_buffer.speech_started" });
  feed(on, { type: "input_audio_buffer.speech_stopped" });
  feed(on, { type: "response.function_call_arguments.done", call_id: "c2", name: "toggle_light", arguments: "{}" });
  setTimeout(() => feed(on, { type: "conversation.item.input_audio_transcription.completed", item_id: "i2", transcript: "Turn it off." }), 150);
  await new Promise((r) => setTimeout(r, 500));
  expect(JSON.parse(sent[0].item.output).message).toBe("Turn it off.");
});
