/**
 * RQ-055 (owner P0 da-5fa8c9ef00): "end the call" must stop Aria.
 * Drives the REAL useRealtimeVoice hook (its real stop()) and the REAL
 * createRealtimeHandlers through a faked WebRTC connection, then asserts the
 * data channel, peer and microphone tracks are really closed.
 */
import React, { act } from "react";
import { createRoot } from "react-dom/client";

const mockLog = jest.fn();
const mockConn = { onMessage: null, sent: [], dc: null, pc: null, track: null, creates: 0 };

jest.mock("../api", () => ({ API: "http://api.test/api" }));
jest.mock("../activationClient", () => ({ logActivationClientEvent: jest.fn() }));
jest.mock("../realtimeDiagnostics", () => ({
  logRealtimeEvent: (...a) => mockLog(...a), transcriptionConfidence: () => null, LOW_CONFIDENCE_THRESHOLD: 0.5,
}));
jest.mock("../realtimeOperationsTools", () => ({ executeOperationsTool: jest.fn(async () => null) }));
jest.mock("../realtimeDisplayTools", () => ({ executeDisplayTool: jest.fn(async () => null) }));
jest.mock("../realtimeCareControl", () => ({ executeCareTool: jest.fn(async () => null), ringLiveLineOnSilence: jest.fn() }));
jest.mock("../realtimeConnection", () => {
  const { createRealtimeHandlers } = require("../realtimeMessageHandler");
  return {
    connectRealtimeVoice: async (p) => {
      const myGen = ++p.startGenRef.current;
      mockConn.creates += 1;
      mockConn.sent = [];
      mockConn.track = { stop: jest.fn() };
      mockConn.dc = { close: jest.fn(), readyState: "open" };
      mockConn.pc = { close: jest.fn(), getSenders: () => [{ track: mockConn.track }] };
      p.dcRef.current = mockConn.dc; p.pcRef.current = mockConn.pc;
      p.localStreamRef.current = { getTracks: () => [mockConn.track] };
      p.sessionIdRef.current = `rt_test_${mockConn.creates}`;
      const { onMessage } = createRealtimeHandlers({
        myGen, startGenRef: p.startGenRef, sessionIdRef: p.sessionIdRef, ctxRef: p.ctxRef,
        caos: { turn_detection: { type: "server_vad" } }, send: (m) => mockConn.sent.push(m),
        stop: p.stop, onEndCall: p.onEndCall, turnSuspectRef: p.turnSuspectRef,
        assistantSpeakingRef: p.assistantSpeakingRef, restingRef: p.restingRef,
        greetingCreateResponseOffRef: p.greetingCreateResponseOffRef, setStatus: p.setStatus,
        setResting: p.setResting, setTranscript: p.setTranscript, setError: p.setError,
        startAwaitingAnswerTimer: p.startAwaitingAnswerTimer, onSpeechEvent: jest.fn(),
        onFirstSpeechStarted: jest.fn(), typedTurnRef: p.typedTurnRef,
      });
      mockConn.onMessage = onMessage;
    },
  };
});

const { useRealtimeVoice } = require("../useRealtimeVoice");
const { resetEndingState } = require("../endingPhrases");

globalThis.IS_REACT_ACT_ENVIRONMENT = true;
let root, container, api, onEndCall;
function Harness() { api = useRealtimeVoice({ room: "214", kioskId: "kio_1", onEndCall }); return null; }

const msg = async (o) => { await act(async () => { mockConn.onMessage({ data: JSON.stringify(o) }); await Promise.resolve(); }); };
const said = (text) => msg({ type: "conversation.item.input_audio_transcription.completed", transcript: text, item_id: `i_${Math.random()}` });
const toolCall = (name, n = 1) => msg({ type: "response.function_call_arguments.done", call_id: `c${n}`, name, arguments: "{}" });
const settle = async (ms = 0) => { await act(async () => { jest.advanceTimersByTime(ms); await Promise.resolve(); await Promise.resolve(); }); };
const finishGoodbye = async () => {
  await msg({ type: "response.created", response: { id: "r_bye" } });
  await msg({ type: "output_audio_buffer.started" });
  await msg({ type: "output_audio_buffer.stopped" });
  await settle(500);
};
const closed = () => ({ track: mockConn.track.stop.mock.calls.length > 0, pc: mockConn.pc.close.mock.calls.length > 0, dc: mockConn.dc.close.mock.calls.length > 0 });
const types = () => mockConn.sent.map((m) => m.type);
const logged = (name) => mockLog.mock.calls.filter((c) => c[1] === name);

beforeEach(async () => {
  jest.useFakeTimers();
  global.fetch = jest.fn(async () => ({ ok: true, json: async () => ({}) }));
  mockLog.mockClear(); resetEndingState(); onEndCall = jest.fn(); mockConn.creates = 0;
  container = document.createElement("div"); root = createRoot(container);
  await act(async () => { root.render(<Harness />); });
  await act(async () => { await api.start(); });
});
afterEach(async () => { await act(async () => { root.unmount(); }); jest.useRealTimers(); });

test("a clear spoken ending is ACKNOWLEDGED aloud, then closes channel, peer and microphone; nothing restarts the call", async () => {
  await said("Aria. Goodbye. End the call.");
  const bye = mockConn.sent.find((m) => m.type === "response.create");
  expect(bye.response.instructions).toMatch(/goodbye/i);                          // an audible goodbye is requested
  expect(types()).toEqual(expect.arrayContaining(["response.cancel", "output_audio_buffer.clear"]));
  expect(closed()).toEqual({ track: false, pc: false, dc: false });               // not cut off before it is heard
  const before = mockConn.sent.length;
  await toolCall("request_staff_help");                                           // ignored while ending
  await said("Hello again");
  expect(mockConn.sent.length).toBe(before);
  await finishGoodbye();
  expect(closed()).toEqual({ track: true, pc: true, dc: true });
  expect(onEndCall).toHaveBeenCalledTimes(1);
  expect(logged("local_end")).toHaveLength(1);
  expect(logged("session_ended")[0][2].meta.reason).toBe("resident_end_call");
  const after = mockConn.sent.length;
  await msg({ type: "response.created", response: { id: "r_stale" } });          // stale response must not resurrect anything
  expect(mockConn.sent.length).toBe(after);
});

test("if the goodbye audio never arrives the call still closes within the 7 s ceiling", async () => {
  await said("End the call.");
  await settle(7000);
  expect(closed()).toEqual({ track: true, pc: true, dc: true });
  expect(onEndCall).toHaveBeenCalledTimes(1);
});

test("repeated explicit stops, in one turn and across turns, end the call exactly once", async () => {
  for (const t of ["End the call.", "Goodbye.", "Go away.", "End the call. Goodbye."]) await said(t);
  expect(mockConn.sent.filter((m) => m.type === "response.create")).toHaveLength(1);   // one goodbye, not four
  await finishGoodbye();
  expect(onEndCall).toHaveBeenCalledTimes(1);
  expect(closed()).toEqual({ track: true, pc: true, dc: true });
  await act(async () => { api.stop("ui_end_call_button"); api.stop("ui_end_call_button"); });
  expect(closed()).toEqual({ track: true, pc: true, dc: true });
});

test("while Aria is speaking, a clear 'end the call' barge-in still ends it", async () => {
  await msg({ type: "output_audio_buffer.started" });
  await msg({ type: "input_audio_buffer.speech_started" });
  await said("End the call.");
  await finishGoodbye();
  expect(closed().track).toBe(true);
  expect(onEndCall).toHaveBeenCalledTimes(1);
});

test("Aria's own goodbye coming back through the speaker (echo) does not end the call", async () => {
  await msg({ type: "response.output_audio_transcript.done", transcript: "Goodbye for now." });
  await msg({ type: "output_audio_buffer.started" });
  await msg({ type: "input_audio_buffer.speech_started" });
  await said("Goodbye.");
  expect(closed()).toEqual({ track: false, pc: false, dc: false });
  expect(onEndCall).not.toHaveBeenCalled();
});

test("FALSE-POSITIVE TEST (quoted sentence / meta statement / question - NOT the rule for Goodbye): these do not end the call", async () => {
  for (const t of ['When I say "goodbye" you stop.', "Can you end the call?", "Don't hang up.", "Please keep talking.", "Say goodbye to my wife for me."]) await said(t);
  expect(closed()).toEqual({ track: false, pc: false, dc: false });
  expect(onEndCall).not.toHaveBeenCalled();
});

test("transcript lost (foreign-language gibberish): the model's second end_call in a row is granted, no more asking", async () => {
  await said("Labai ačiū.");
  await toolCall("end_call", 1);
  expect(closed().track).toBe(false);                              // first attempt: one question
  expect(types()).toContain("response.create");
  await said("لابيانو");
  await toolCall("end_call", 2);
  expect(logged("end_call_corroborated")).toHaveLength(1);
  await settle(7000);                                          // goodbye audio never arrives: 7 s ceiling
  expect(closed()).toEqual({ track: true, pc: true, dc: true });
  expect(onEndCall).toHaveBeenCalledTimes(1);
  await toolCall("end_call", 3);                               // immediate extra end_call: idempotent
  await settle(8000);
  expect(onEndCall).toHaveBeenCalledTimes(1);
});

test("standalone Goodbye, End the call and Go away each end the call immediately", async () => {
  for (const phrase of ["Goodbye.", "End the call.", "Go away."]) {
    await act(async () => { api.stop("test_reset"); });
    await act(async () => { await api.start(); });
    onEndCall.mockClear();
    await said(phrase);
    await finishGoodbye();
    expect(onEndCall).toHaveBeenCalledTimes(1);
    expect(closed().track).toBe(true);
  }
});

test("model end_call on an out-of-script transcript (Korean/Arabic mis-detection) is granted on the FIRST attempt", async () => {
  await said("안녕하세요.");
  await toolCall("end_call", 1);
  expect(logged("end_call_corroborated")[0][2].meta.via).toBe("out_of_script_transcript");
  await settle(7000);
  expect(closed().track).toBe(true);
  expect(onEndCall).toHaveBeenCalledTimes(1);
});

test("a single end_call on a Latin-script transcript that says nothing about ending is still questioned (no phantom hang-ups)", async () => {
  await said("Das sind keine.");
  await toolCall("end_call", 1);
  await settle(8000);
  expect(closed().track).toBe(false);
});

test("page reload / unmount stops the microphone", async () => {
  await act(async () => { root.unmount(); });
  expect(closed().track).toBe(true);
  root = createRoot(container);
  await act(async () => { root.render(<Harness />); });
});

test("after an ended call a deliberate new start works, and the old connection stays dead", async () => {
  const oldHandler = mockConn.onMessage;
  await said("Goodbye.");
  await finishGoodbye();
  expect(onEndCall).toHaveBeenCalledTimes(1);
  await act(async () => { await api.start(); });                // new wake / UI start
  expect(mockConn.creates).toBe(2);
  expect(closed()).toEqual({ track: false, pc: false, dc: false });         // new fakes, nothing closed yet
  await said("Hello Aria, how are you?");
  expect(api.transcript.at(-1).text).toBe("Hello Aria, how are you?");
  await act(async () => { oldHandler({ data: JSON.stringify({ type: "conversation.item.input_audio_transcription.completed", transcript: "Goodbye." }) }); });
  expect(onEndCall).toHaveBeenCalledTimes(1);
});
