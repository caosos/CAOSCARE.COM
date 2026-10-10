const mockLog = jest.fn();
jest.mock("../api", () => ({ API: "http://api.test/api" }));
jest.mock("../realtimeDiagnostics", () => ({
  logRealtimeEvent: (...a) => mockLog(...a), transcriptionConfidence: () => null, LOW_CONFIDENCE_THRESHOLD: 0.5,
}));
jest.mock("../realtimeDeviceTools", () => ({ executeDeviceTool: jest.fn(async () => null) }));
jest.mock("../realtimeOperationsTools", () => ({ executeOperationsTool: jest.fn(async () => null) }));
jest.mock("../realtimeDisplayTools", () => ({ executeDisplayTool: jest.fn(async () => null) }));
jest.mock("../realtimeCareControl", () => ({ executeCareTool: jest.fn(async () => null), ringLiveLineOnSilence: jest.fn() }));
import { createDeltaLead } from "../deltaLead";
import { createRealtimeHandlers } from "../realtimeMessageHandler";

test("lead and characters streamed before playback, from a fixture with a fake clock", () => {
  let t = 1000; const log = jest.fn();
  const d = createDeltaLead(log, () => t);
  d.onDelta({ response_id: "r1", delta: "I have " });
  t = 1180; d.onDelta({ response_id: "r1", delta: "notified the nurse." });
  t = 1450; d.onAudioStarted({ response_id: "r1" });
  expect(log).toHaveBeenCalledWith("transcript_delta_lead", { meta: { response_id: "r1", lead_ms: 450, chars_before_audio: 26, total_chars_at_report: 26 } });
  d.onResponseDone({ id: "r1" });
  expect(log).toHaveBeenCalledTimes(1);   // reported once only
});

test("audio started without response_id pairs with the latest streaming response", () => {
  let t = 0; const log = jest.fn(); const d = createDeltaLead(log, () => t);
  d.onDelta({ response_id: "r2", delta: "abc" }); t = 200; d.onAudioStarted({});
  expect(log.mock.calls[0][1].meta).toMatchObject({ response_id: "r2", lead_ms: 200 });
});

test("a response whose audio never starts reports null (nothing was heard)", () => {
  const log = jest.fn(); const d = createDeltaLead(log, () => 5);
  d.onDelta({ response_id: "r3", delta: "text" }); d.onResponseDone({ id: "r3" });
  expect(log.mock.calls[0][1].meta).toMatchObject({ response_id: "r3", lead_ms: null, chars_before_audio: null, total_chars_at_report: 4 });
});

test("wired into the real handler: delta, audio start, response.done", () => {
  mockLog.mockClear();
  const on = createRealtimeHandlers({
    myGen: 1, startGenRef: { current: 1 }, sessionIdRef: { current: "rt_dl" }, ctxRef: { current: {} },
    caos: {}, send: jest.fn(), stop: jest.fn(), onEndCall: jest.fn(),
    turnSuspectRef: { current: false }, assistantSpeakingRef: { current: false }, restingRef: { current: false },
    greetingCreateResponseOffRef: { current: false }, setStatus: jest.fn(), setResting: jest.fn(),
    setTranscript: jest.fn(), setError: jest.fn(), startAwaitingAnswerTimer: jest.fn(), onSpeechEvent: jest.fn(), onFirstSpeechStarted: jest.fn(),
  }).onMessage;
  const feed = (o) => on({ data: JSON.stringify(o) });
  feed({ type: "response.output_audio_transcript.delta", response_id: "rw", delta: "Hello there" });
  feed({ type: "output_audio_buffer.started", response_id: "rw" });
  feed({ type: "response.done", response: { id: "rw", output: [] } });
  const ev = mockLog.mock.calls.filter((c) => c[1] === "transcript_delta_lead");
  expect(ev).toHaveLength(1);
  expect(ev[0][2].meta).toMatchObject({ response_id: "rw", chars_before_audio: 11 });
});
