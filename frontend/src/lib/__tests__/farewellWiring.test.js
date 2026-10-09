/**
 * RQ-051 audit F2/F3/F4: removing the claimGuard / farewellWatch calls from
 * realtimeMessageHandler.js used to leave every test green. These drive the
 * real handler so a removed wiring fails here.
 */
const mockLog = jest.fn();
jest.mock("../api", () => ({ API: "http://api.test/api" }));
jest.mock("../realtimeDiagnostics", () => ({
  logRealtimeEvent: (...a) => mockLog(...a), transcriptionConfidence: () => null, LOW_CONFIDENCE_THRESHOLD: 0.5,
}));
jest.mock("../realtimeDeviceTools", () => ({ executeDeviceTool: jest.fn(async () => null) }));
jest.mock("../realtimeOperationsTools", () => ({ executeOperationsTool: jest.fn(async () => null) }));
jest.mock("../realtimeDisplayTools", () => ({ executeDisplayTool: jest.fn(async () => null) }));
jest.mock("../realtimeCareControl", () => ({ executeCareTool: jest.fn(async () => null), ringLiveLineOnSilence: jest.fn() }));
import { createRealtimeHandlers } from "../realtimeMessageHandler";

function handler() {
  const startGenRef = { current: 1 };
  return createRealtimeHandlers({
    myGen: 1, startGenRef, sessionIdRef: { current: "rt_w" }, ctxRef: { current: { room: "214" } },
    caos: {}, send: jest.fn(), stop: jest.fn(), onEndCall: jest.fn(),
    turnSuspectRef: { current: false }, assistantSpeakingRef: { current: false }, restingRef: { current: false },
    greetingCreateResponseOffRef: { current: false }, setStatus: jest.fn(), setResting: jest.fn(),
    setTranscript: jest.fn(), setError: jest.fn(), startAwaitingAnswerTimer: jest.fn(), onSpeechEvent: jest.fn(), onFirstSpeechStarted: jest.fn(),
  }).onMessage;
}
const feed = (on, o) => on({ data: JSON.stringify(o) });
const loggedTypes = () => mockLog.mock.calls.map((c) => c[1]);
beforeEach(() => mockLog.mockClear());

test("F4: a spoken goodbye with no end_call is logged on response.done", () => {
  const on = handler();
  feed(on, { type: "response.output_audio_transcript.done", transcript: "Goodnight, Michael. Take care." });
  feed(on, { type: "response.done", response: { id: "r1", output: [] } });
  expect(loggedTypes()).toContain("farewell_without_end_call");
});

test("F2: an unsupported action claim is logged on response.done", () => {
  const on = handler();
  feed(on, { type: "response.output_audio_transcript.done", transcript: "I've notified the nurse and she is on her way." });
  feed(on, { type: "response.done", response: { id: "r2", output: [] } });
  expect(loggedTypes()).toContain("unsupported_action_claim");
});
