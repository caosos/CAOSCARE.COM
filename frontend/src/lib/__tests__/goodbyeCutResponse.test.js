/**
 * A goodbye closes the call, and the reply it cut off is not Aria's turn
 * (aria-room-conversation-cleanup-002).
 *
 * Scratch Room 214 rt_10s3ng43_1792142773769 (2026-10-16 09:26:33Z): the server's
 * auto-response to "Thanks, that will be all. Goodbye." started before the
 * transcript arrived; the model was narrating its end_call ("Okay, thanks for the
 * chat-let me take care of that for you now."); the local goodbye cancelled it
 * ~200 ms in, but the whole line was still shown and saved as hers. Replays that
 * sequence through the REAL hook + handler and asserts: one scripted goodbye,
 * nothing promised in the record, channel/peer/mic closed, lease released,
 * onEndCall (the kiosk's TV/speaker restore) called once.
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
      p.leaseRoomRef.current = { room: "214", sessionId: p.sessionIdRef.current };
      p.ctxRef.current = { ...(p.ctxRef.current || {}), resident_id: "res_goodbye_test" };
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

const { GOODBYE_INSTRUCTIONS } = require("../endController");
const PROMISE = "Okay, thanks for the chat—let me take care of that for you now.";
const savedTurns = () => global.fetch.mock.calls.filter(([u]) => String(u).includes("/memory/realtime-turn"))
  .map(([, o]) => JSON.parse(o.body)).map((b) => `${b.role}: ${b.text}`);
const released = () => global.fetch.mock.calls.filter(([u]) => String(u).includes("/realtime/room/214/release"));
const goodbyeRequests = () => mockConn.sent.filter((m) => m.type === "response.create" && m.response?.instructions === GOODBYE_INSTRUCTIONS);

async function goodbyeRun(words) {
  await msg({ type: "input_audio_buffer.speech_stopped" });
  await msg({ type: "response.created", response: { id: "r_auto" } });
  await msg({ type: "output_audio_buffer.started" });
  await said(words);                                                               // local end: cancel + clear
  await msg({ type: "output_audio_buffer.cleared" });
  await msg({ type: "response.output_audio_transcript.done", response_id: "r_auto", item_id: "it_auto", transcript: PROMISE });
  await msg({ type: "response.done", response: { id: "r_auto", status: "cancelled" } });
  await msg({ type: "response.created", response: { id: "r_bye" } });
  await msg({ type: "output_audio_buffer.started" });
  await msg({ type: "response.output_audio_transcript.done", response_id: "r_bye", item_id: "it_bye", transcript: "Okay, bye for now." });
  await msg({ type: "response.done", response: { id: "r_bye", status: "completed" } });
  await msg({ type: "output_audio_buffer.stopped" });
  await settle(8000);
}

test("the scratch sequence: the cut promise is diagnostics only, the scripted goodbye is her turn, everything closes", async () => {
  await goodbyeRun("Thanks, that will be all. Goodbye.");
  const turns = savedTurns();
  expect(turns).toContain("user: Thanks, that will be all. Goodbye.");
  expect(turns).toContain("assistant: Okay, bye for now.");
  expect(turns.join("\n")).not.toMatch(/take care of that/);
  expect(api.transcript.map((t) => t.text).join("\n")).not.toMatch(/take care of that/);
  const cut = logged("assistant_transcript_cut_by_goodbye");
  expect(cut).toHaveLength(1);
  expect(cut[0][2]).toMatchObject({ text: PROMISE, responseId: "r_auto" });
  expect(types()).toContain("response.cancel");
  expect(goodbyeRequests()).toHaveLength(1);                                       // exactly one goodbye
  expect(closed()).toEqual({ track: true, pc: true, dc: true });
  expect(released()).toHaveLength(1);                                              // lease released
  expect(onEndCall).toHaveBeenCalledTimes(1);                                      // kiosk restores TV/speaker here
});

test.each([
  "Goodbye.", "Talk to you later.", "That's all.", "Good night.", "Okay, good night, Aria.",
  "That's all for now, thanks.", "Alright, talk to you later, bye.", "I'll talk to you later, goodbye.",
])("%s closes deterministically with one goodbye and no cut words saved", async (words) => {
  await goodbyeRun(words);
  expect(goodbyeRequests()).toHaveLength(1);
  expect(savedTurns().join("\n")).not.toMatch(/take care of that/);
  expect(closed()).toEqual({ track: true, pc: true, dc: true });
  expect(released()).toHaveLength(1);
  expect(onEndCall).toHaveBeenCalledTimes(1);
});

test("a reply that finished BEFORE the goodbye is still her turn", async () => {
  await msg({ type: "response.created", response: { id: "r_earlier" } });
  await msg({ type: "response.output_audio_transcript.done", response_id: "r_earlier", item_id: "it_e", transcript: "The desk lamp is on." });
  await msg({ type: "response.done", response: { id: "r_earlier", status: "completed" } });
  await goodbyeRun("Goodbye.");
  expect(savedTurns()).toContain("assistant: The desk lamp is on.");
  expect(logged("assistant_transcript_cut_by_goodbye")).toHaveLength(1);
});
