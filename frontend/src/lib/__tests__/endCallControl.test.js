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
const mockMicSeg = { current: null };   // the level meter's open voice segment (micLevelTelemetry.js), or null

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
  const { createMicVoice } = jest.requireActual("../micLevelTelemetry");
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
      const micVoice = createMicVoice();
      micVoice.attach(() => mockMicSeg.current);
      const { onMessage } = createRealtimeHandlers({
        myGen, startGenRef: p.startGenRef, sessionIdRef: p.sessionIdRef, ctxRef: p.ctxRef,
        caos: { turn_detection: { type: "server_vad" } }, send: (m) => mockConn.sent.push(m),
        stop: p.stop, onEndCall: p.onEndCall, turnSuspectRef: p.turnSuspectRef,
        assistantSpeakingRef: p.assistantSpeakingRef, restingRef: p.restingRef,
        greetingCreateResponseOffRef: p.greetingCreateResponseOffRef, setStatus: p.setStatus,
        setResting: p.setResting, setTranscript: p.setTranscript, setError: p.setError,
        startAwaitingAnswerTimer: p.startAwaitingAnswerTimer, onSpeechEvent: jest.fn(),
        onFirstSpeechStarted: jest.fn(), typedTurnRef: p.typedTurnRef, micVoice,
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
  mockLog.mockClear(); resetEndingState(); onEndCall = jest.fn(); mockConn.creates = 0; mockMicSeg.current = null;
  container = document.createElement("div"); root = createRoot(container);
  await act(async () => { root.render(<Harness />); });
  await act(async () => { await api.start(); });
});
afterEach(async () => { await act(async () => { root.unmount(); }); jest.useRealTimers(); });

test("a clear spoken ending is ACKNOWLEDGED aloud, then closes channel, peer and microphone; nothing restarts the call", async () => {
  await said("Aria. Goodbye. End the call.");
  const bye = mockConn.sent.find((m) => m.type === "response.create");
  expect(bye.response.instructions).toMatch(/goodbye/i);                          // an audible goodbye is requested
  expect(types()).toContain("output_audio_buffer.clear");                         // nothing in flight, so nothing to cancel
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

test("a reply already in flight when 'Goodbye' is heard is cancelled first; the goodbye is requested only after it finishes (the 01:00:50 silent case)", async () => {
  await msg({ type: "response.created", response: { id: "r_auto" } });        // server auto-reply to the utterance
  await said("Goodbye.");
  expect(types()).toContain("response.cancel");
  expect(types()).not.toContain("response.create");                          // must not collide with the live reply
  await msg({ type: "response.done", response: { id: "r_auto" } });
  expect(mockConn.sent.filter((m) => m.type === "response.create")).toHaveLength(1);
  await finishGoodbye();
  expect(closed().track).toBe(true);
  expect(logged("call_closed")[0][2].meta.goodbye_audio_played).toBe(true);
});

const BYE = { caos_goodbye: "1" };
const creates = () => mockConn.sent.filter((m) => m.type === "response.create");

test("a goodbye response that produced no audio is retried once, after a grace for its audio", async () => {
  await said("Goodbye.");
  expect(creates()[0].response.metadata).toEqual(BYE);
  await msg({ type: "response.created", response: { id: "r1", metadata: BYE } });
  await msg({ type: "response.done", response: { id: "r1", metadata: BYE } });   // no output_audio_buffer.started
  expect(creates()).toHaveLength(1);                                            // done can come before the audio
  await settle(2500);
  expect(creates()).toHaveLength(2);
  await finishGoodbye();
  expect(onEndCall).toHaveBeenCalledTimes(1);
});

test("goodbye while waiting for its audio: done before audio is not retried (one goodbye, said once)", async () => {
  await said("That will be all for now.");
  await msg({ type: "response.created", response: { id: "r_auto" } });        // the reply the goodbye cut
  await msg({ type: "response.done", response: { id: "r_auto", status: "cancelled" } });
  await msg({ type: "response.created", response: { id: "r1", metadata: BYE } });
  await msg({ type: "response.done", response: { id: "r1", metadata: BYE } });
  await settle(200);
  await msg({ type: "output_audio_buffer.started" });                         // its audio, 200 ms after done
  await settle(3000);
  expect(creates()).toHaveLength(1);
  await msg({ type: "output_audio_buffer.stopped" });
  await settle(500);
  expect(onEndCall).toHaveBeenCalledTimes(1);
  expect(logged("call_closed")).toHaveLength(1);
});

test("goodbye while a reply is being composed: the goodbye waits for it, then is asked for once", async () => {
  await msg({ type: "response.created", response: { id: "r_reply" } });       // composing, nothing audible yet
  await said("Goodbye.");
  expect(creates()).toHaveLength(0);
  expect(types()).toContain("response.cancel");
  await msg({ type: "response.done", response: { id: "r_reply", status: "cancelled" } });
  await msg({ type: "response.done", response: { id: "r_reply", status: "cancelled" } });   // a repeated done
  expect(creates()).toHaveLength(1);
  await finishGoodbye();
  expect(onEndCall).toHaveBeenCalledTimes(1);
});

test("goodbye while she is speaking: her speech is cleared and one goodbye follows", async () => {
  await msg({ type: "response.created", response: { id: "r_reply" } });
  await msg({ type: "output_audio_buffer.started" });
  await said("Goodbye.");
  expect(types()).toEqual(expect.arrayContaining(["response.cancel", "output_audio_buffer.clear"]));
  await msg({ type: "response.done", response: { id: "r_reply", status: "cancelled" } });
  await msg({ type: "output_audio_buffer.cleared" });
  expect(creates()).toHaveLength(1);
  await msg({ type: "response.created", response: { id: "r1", metadata: BYE } });
  await msg({ type: "response.done", response: { id: "r1", metadata: BYE } });
  await msg({ type: "output_audio_buffer.started" });
  await settle(3000);
  expect(creates()).toHaveLength(1);
  await msg({ type: "output_audio_buffer.stopped" });
  await settle(500);
  expect(onEndCall).toHaveBeenCalledTimes(1);
});

test("if no goodbye audio ever plays, a local spoken 'Goodbye.' is used before closing", async () => {
  const spoken = [];
  window.speechSynthesis = { speak: (u) => { spoken.push(u.text); setTimeout(() => u.onend && u.onend(), 300); } };
  global.SpeechSynthesisUtterance = function (t) { this.text = t; };
  try {
    await said("End the call.");
    await settle(7000);                                                       // model produced nothing: ceiling reached
    expect(spoken).toEqual(["Goodbye."]);
    await settle(400);
    expect(closed().track).toBe(true);
    const meta = logged("call_closed")[0][2].meta;
    expect(meta.local_fallback_used).toBe(true);
    expect(meta.goodbye_audio_played).toBe(false);
  } finally { delete window.speechSynthesis; delete global.SpeechSynthesisUtterance; }
});

test("the goodbye transcript is still recorded while closing", async () => {
  await said("Goodbye.");
  await msg({ type: "response.output_audio_transcript.done", transcript: "Goodbye, I'm right here when you call." });
  expect(logged("assistant_transcript")).toHaveLength(1);
  expect(logged("farewell_without_end_call")).toHaveLength(0);
  await finishGoodbye();
});

// Room 214, 2026-10-12 12:56 (rt_zi8umtl0): the model's end_call arrived 120 ms before the
// "That'll be all for now." transcript. The transcript began the goodbye while end_call had no
// output, so Aria said "Okay, I'm still waiting on that to finish." The open call must be
// answered before the goodbye is requested, and the goodbye just echoes theirs.
// Room 214 rt_qppzkpzp_1792642914139 (2026-10-21 23:22 CDT): a ~0.2 s sound under Aria's speech came back
// as "That's all" (uncertain_fragment) and the page hung up. Timings below are that call's, in ms.
const turn = async ({ id, text, gapMs = null, ariaBetween = false, overlap = false, segmentMs = 1200 }) => {
  if (gapMs !== null) {
    await msg({ type: "input_audio_buffer.speech_stopped", item_id: `${id}_prev` });
    if (ariaBetween) { await msg({ type: "output_audio_buffer.started" }); await msg({ type: "output_audio_buffer.stopped" }); }
    await settle(gapMs);
  }
  if (overlap) await msg({ type: "output_audio_buffer.started" });
  await msg({ type: "input_audio_buffer.speech_started", item_id: id });
  if (overlap) await msg({ type: "output_audio_buffer.stopped" });
  await settle(segmentMs);
  await msg({ type: "input_audio_buffer.speech_stopped", item_id: id });
  await msg({ type: "conversation.item.input_audio_transcription.completed", transcript: text, item_id: id });
};
const lastUserMeta = () => logged("user_transcript").slice(-1)[0][2].meta;

test("rt_qppzkpzp: 'That's all' heard only as an uncertain overlap of Aria's speech does not end the call", async () => {
  await msg({ type: "input_audio_buffer.speech_stopped", item_id: "i_prev" });                       // 43.826
  await said("that you say so, that way I'm not wondering if it actually connected or not.");     // 44.449
  await msg({ type: "response.created", response: { id: "r_fair" } });
  await settle(690);
  await msg({ type: "output_audio_buffer.started" });                                              // 44.516
  await settle(1567);
  await msg({ type: "input_audio_buffer.speech_started", item_id: "i_x" });                        // 46.083, Aria still playing
  await msg({ type: "output_audio_buffer.stopped" });                                              // 46.086 cleared
  await msg({ type: "response.output_audio_transcript.done", transcript: "Fair point, Michael. I can do that." });
  await settle(1117);
  await msg({ type: "input_audio_buffer.speech_stopped", item_id: "i_x" });                        // 47.203 (1,120 ms segment)
  await msg({ type: "conversation.item.input_audio_transcription.completed", transcript: "That's all", item_id: "i_x" });
  const meta = lastUserMeta();
  expect(meta.turn_class_reason).toBe("uncertain_fragment");
  expect(meta.end_intent).toBe("none");
  expect(meta.soft_ending_overlap_held).toBe(true);
  expect(logged("local_end")).toHaveLength(0);
  await settle(8000);
  expect(closed()).toEqual({ track: false, pc: false, dc: false });
  expect(onEndCall).not.toHaveBeenCalled();
});

test("rt_qppzkpzp: the model's end_call on that same uncertain 'That's all' is questioned, not granted", async () => {
  await turn({ id: "i_x", text: "That's all", overlap: true, segmentMs: 1120 });
  await toolCall("end_call");
  await settle(8000);
  expect(closed().track).toBe(false);
  expect(onEndCall).not.toHaveBeenCalled();
});

test.each(["Goodbye.", "Bye.", "Goodnight.", "Hang up."])(
  "a clear '%s' in the same uncertain overlap still ends the call, recorded as via transcript", async (text) => {
    await turn({ id: "i_x", text, overlap: true, segmentMs: 1120 });
    expect(lastUserMeta().turn_class_reason).toBe("uncertain_fragment");
    expect(logged("local_end")).toHaveLength(1);
    await finishGoodbye();
    expect(onEndCall).toHaveBeenCalledTimes(1);
    expect(logged("call_closed")[0][2].meta.via).toBe("transcript");
  });

test("a granted model end_call is still recorded as via end_call_tool", async () => {
  await said("안녕하세요.");   // no local match; the model's end_call is granted (out-of-script transcript)
  await toolCall("end_call", 1);
  await finishGoodbye();
  expect(logged("local_end")).toHaveLength(0);
  expect(onEndCall).toHaveBeenCalledTimes(1);
  expect(logged("call_closed")[0][2].meta.via).toBe("end_call_tool");
});

// Michael's most recent transcript endings in Room 214 (2026-10-18..21), with their recorded turn class,
// segment length, gap after the previous segment and whether Aria's audio played in between. 2026-10-22: the
// 10-21 06:14 "Goodbye" (rt_r7yjpasv) left this list - its mic record matches rt_4ze7jvrt (DISPUTED below).
const GENUINE = [
  ["goodbye", "no_overlap", 969, 2308, true],
  ["That'll be all for now, thank you.", "no_overlap", 3145, 29101, true],
  ["No, that'll be all for now. Hang up.", "no_overlap", 3340, 5617, true],
  ["That'll be all, goodnight.", "no_overlap", 4226, 4775, true],
  ["Go away.", "no_overlap", 1055, 12775, true],
  ["Alright, that'll be all for now, thank you.", "coherent_barge_in", 3967, 1239, true],
  ["That'll be all for now.", "coherent_barge_in", 3062, 858, true],
  ["Okay, well that'll be all for now. I appreciate it.", "coherent_barge_in", 4169, 16921, true],
  ["That's all.", "no_overlap", 1726, null, false],
  ["Goodbye.", "no_overlap", 3851, null, false],
  ["That'll be all for now. Thank you.", "no_overlap", 2065, 8193, true],
  ["That'll be all.", "no_overlap", 1270, 18284, true],
  ["Aria, good night.", "no_overlap", 2174, 4187, false],
  ["Goodbye.", "no_overlap", 1155, 27394, true],
];
test.each(GENUINE)("genuine ending %p (%s) still ends the call", async (text, cls, segmentMs, gapMs, ariaBetween) => {
  await turn({ id: "i_end", text, gapMs, ariaBetween, overlap: cls === "coherent_barge_in", segmentMs });
  expect(lastUserMeta().turn_class_reason).toBe(cls);
  expect(lastUserMeta().end_intent).toBe("explicit");
  await finishGoodbye();
  expect(onEndCall).toHaveBeenCalledTimes(1);
  expect(logged("call_closed")[0][2].meta.via).toBe("transcript");
});


// Room 214 rt_4ze7jvrt_1792654375803 (2026-10-22 02:33 CDT). Owner: he was still talking and said nothing like
// a goodbye. Server speech_started 15.311, speech_stopped 16.468 (1,157 ms: ~0.16 s of speech + 1 s "silence"),
// transcript "go away" (no_overlap) 17.009, page hung up 17.013. The eMeet and the processed track both carried
// his voice continuously from ~15.13 to ~17.43. ms below are relative to the transcript.
const cutTurn = async ({ id, text, segmentMs, stoppedBeforeMs, voice = null, overlap = false }) => {
  const T = Date.now() + segmentMs + stoppedBeforeMs;   // the moment the transcript lands
  mockMicSeg.current = null;
  if (overlap) await msg({ type: "output_audio_buffer.started" });
  await msg({ type: "input_audio_buffer.speech_started", item_id: id });
  if (overlap) await msg({ type: "output_audio_buffer.stopped" });
  await settle(segmentMs);
  await msg({ type: "input_audio_buffer.speech_stopped", item_id: id });
  await settle(stoppedBeforeMs);
  // voice = [startMs, lastVoicedMs] of the meter segment open at T (lastVoicedMs 0 = voiced right now)
  if (voice) mockMicSeg.current = { startAt: T + voice[0], voiceAt: T + voice[1] };
  await msg({ type: "conversation.item.input_audio_transcription.completed", transcript: text, item_id: id });
};

test("rt_4ze7jvrt: 'go away' cut from a turn he was still speaking does not end the call", async () => {
  await cutTurn({ id: "i_go", text: "go away", segmentMs: 1157, stoppedBeforeMs: 540, voice: [-1880, 0] });
  const meta = lastUserMeta();
  expect(meta.turn_class_reason).toBe("no_overlap");
  expect(meta.end_intent).toBe("none");
  expect(meta.ending_held_still_talking).toBe(true);
  expect(logged("local_end")).toHaveLength(0);
  await settle(8000);
  expect(closed()).toEqual({ track: false, pc: false, dc: false });
  expect(onEndCall).not.toHaveBeenCalled();
});

test("rt_4ze7jvrt: the model's end_call on that held 'go away' is questioned, not granted", async () => {
  await cutTurn({ id: "i_go", text: "go away", segmentMs: 1157, stoppedBeforeMs: 540, voice: [-1880, 0] });
  await toolCall("end_call", 1);
  await settle(8000);
  expect(logged("tool_result").slice(-1)[0][2].meta.result.ok).toBe(false);
  expect(closed().track).toBe(false);
  expect(onEndCall).not.toHaveBeenCalled();
});

test("the same 'go away' after his voice stopped (no open meter segment) still ends the call", async () => {
  await cutTurn({ id: "i_go", text: "go away", segmentMs: 1157, stoppedBeforeMs: 540, voice: null });
  expect(lastUserMeta().end_intent).toBe("explicit");
  await finishGoodbye();
  expect(onEndCall).toHaveBeenCalledTimes(1);
  expect(logged("call_closed")[0][2].meta.via).toBe("transcript");
});

// Owner 2026-10-22: "when i did say goodnight that was a question because that's what she said". In
// rt_4ze7jvrt it came after the hang-up was already decided; asked back at any point it is not a goodbye.
test("'Goodnight?' asked back after Aria's own 'Goodnight.' is a question: no close, and end_call is questioned", async () => {
  await msg({ type: "response.created", response: { id: "r_gn" } });
  await msg({ type: "output_audio_buffer.started" });
  await msg({ type: "response.output_audio_transcript.done", transcript: "Goodnight." });
  await msg({ type: "output_audio_buffer.stopped" });
  await settle(1500);
  await cutTurn({ id: "i_gn", text: "Goodnight?", segmentMs: 1300, stoppedBeforeMs: 500 });
  expect(lastUserMeta().end_intent).toBe("none");
  expect(logged("local_end")).toHaveLength(0);
  await toolCall("end_call", 1);
  await settle(8000);
  expect(logged("tool_result").slice(-1)[0][2].meta.result.ok).toBe(false);
  expect(onEndCall).not.toHaveBeenCalled();
});

// Disputed: same mic shape as rt_4ze7jvrt. rt_r7yjpasv (2026-10-21 06:14 CDT): "Goodbye" closed the call while
// the model, answering his audio, replied "Oh, you'd like me to sound like I'm actually you?" - inferred, not
// owner-confirmed, to be a false close.
test("rt_r7yjpasv shape: a one-word 'Goodbye' cut while he was still speaking is held", async () => {
  await cutTurn({ id: "i_gb", text: "Goodbye", segmentMs: 1114, stoppedBeforeMs: 550, voice: [-2500, 0] });
  expect(lastUserMeta().ending_held_still_talking).toBe(true);
  await settle(8000);
  expect(onEndCall).not.toHaveBeenCalled();
});

// Every other ending recorded with the level meter on (Room 214, 2026-10-17..21): text, class, segment ms,
// speech_stopped -> transcript ms, and the meter segment still open at the transcript (null = closed).
const METERED_GENUINE = [
  ["rt_lcnze2u9", "That will be all for now.", "no_overlap", 1799, 20, [-180, 0]],
  ["rt_dla0ej4s", "Okay, that will be all for now, Aria. Thank you.", "no_overlap", 4252, 30, null],
  ["rt_w2yogkau", "Goodbye.", "no_overlap", 1155, 400, null],
  ["rt_3t61un35", "Aria, good night.", "no_overlap", 2174, 340, null],
  ["rt_tacnqxsf", "That'll be all.", "no_overlap", 1270, 310, [-140, 0]],
  ["rt_6it6vqvv", "That'll be all for now. Thank you.", "no_overlap", 2065, 370, null],
  ["rt_uc18ftek", "Goodbye.", "no_overlap", 3851, 760, null],
  ["rt_uhq0rlwt", "That's all.", "no_overlap", 1726, 820, null],
  ["rt_6ewog9gy", "Okay, well that'll be all for now. I appreciate it.", "coherent_barge_in", 4169, 840, null],
  ["rt_y6k2od0z", "That'll be all for now.", "coherent_barge_in", 3062, 550, null],
  ["rt_2vlr67fs", "Alright, that'll be all for now, thank you.", "coherent_barge_in", 3967, 640, null],
  ["rt_7k7c1m3s", "Go away.", "no_overlap", 1055, 530, null],
  ["rt_3bfuhkov", "That'll be all, goodnight.", "no_overlap", 4226, 730, null],
  ["rt_tbfytpqr", "No, that'll be all for now. Hang up.", "no_overlap", 3340, 630, null],
  ["rt_sp1ebszy", "That'll be all for now, thank you.", "no_overlap", 3145, 710, null],
  ["rt_52ayqcen", "goodbye", "no_overlap", 969, 550, null],
];
test.each(METERED_GENUINE)("metered ending %s %p still ends the call", async (sid, text, cls, segmentMs, stoppedBeforeMs, voice) => {
  await cutTurn({ id: "i_end", text, segmentMs, stoppedBeforeMs, voice, overlap: cls === "coherent_barge_in" });
  expect(lastUserMeta().turn_class_reason).toBe(cls);
  expect(lastUserMeta().end_intent).toBe("explicit");
  await finishGoodbye();
  expect(onEndCall).toHaveBeenCalledTimes(1);
  expect(logged("call_closed")[0][2].meta.via).toBe("transcript");
});

test("a goodbye that overtakes Aria's own end_call answers that call first, then says a brief goodbye", async () => {
  await msg({ type: "input_audio_buffer.speech_stopped" });   // transcript for this turn is pending
  // Each act() is awaited before the next: an overlapping act() left React unable to render the next test's
  // harness, so that test drove the previous call's hook (the old "keep this test LAST" leak).
  await toolCall("end_call", 7);                                // waits for the transcript (grounding)
  await said("That'll be all for now.");
  await settle();
  const iOutput = mockConn.sent.findIndex((m) => m.type === "conversation.item.create" && m.item?.call_id === "c7");
  const iBye = mockConn.sent.findIndex((m) => m.type === "response.create");
  expect(iOutput).toBeGreaterThanOrEqual(0);
  expect(iOutput).toBeLessThan(iBye);
  expect(mockConn.sent[iBye].response.instructions).toMatch(/bye for now/i);
  expect(mockConn.sent[iBye].response.instructions).toMatch(/nothing else/i);
  expect(mockConn.sent.filter((m) => m.type === "response.create")).toHaveLength(1);
  await finishGoodbye();
  expect(onEndCall).toHaveBeenCalledTimes(1);
});
