/** Low-cost voice transport (cascadeTransport.js): emits the Realtime events the room handler already uses. */
import { TextEncoder, TextDecoder } from "util";
import { chatMessage, createCascadeConnection, requestedTransport, takeSentences } from "../cascadeTransport";

global.TextEncoder = global.TextEncoder || TextEncoder;
global.TextDecoder = global.TextDecoder || TextDecoder;
const flush = () => new Promise((r) => setTimeout(r, 5));
const GREETING = { instructions: "Say exactly this: \"Hi, Michael.\"", tool_choice: "none" };

class FakeWs {
  constructor() { this.sent = []; this.readyState = 1; FakeWs.last = this; }
  send(m) { this.sent.push(m); }
  close() {}
  serve(obj) { this.onmessage({ data: JSON.stringify(obj) }); }
  json() { return this.sent.filter((m) => typeof m === "string").map((m) => JSON.parse(m)); }
}
class FakeAudioCtx {
  constructor() { this.destination = {}; }
  createMediaStreamSource() { return { connect() {}, disconnect() {} }; }
  createScriptProcessor() { return { connect() {}, disconnect() {} }; }
  close() {}
}
const sse = (events) => {
  const chunks = events.map((e) => new TextEncoder().encode(`data: ${JSON.stringify(e)}\n\n`));
  return { ok: true, body: { getReader: () => ({ read: async () => (chunks.length ? { value: chunks.shift(), done: false } : { done: true }) }) } };
};

function setup({ replies = [], transcript = "I need some water" } = {}) {
  const calls = [];
  const fetchImpl = jest.fn(async (url, opts) => {
    calls.push({ url, opts });
    if (url.endsWith("/transcribe")) return { ok: true, json: async () => ({ text: transcript }) };
    if (url.endsWith("/respond")) return replies.length ? replies.shift()(opts) : sse([{ type: "done" }]);
    return { ok: true, json: async () => ({ ok: true }) };
  });
  const player = { playing: false, play: jest.fn(), stop: jest.fn(() => false), close: jest.fn() };
  const { dc, pc } = createCascadeConnection({
    session: { token: "tok_secret_value", session: { model: "gpt-4o-mini" } },
    caos: { greeting: GREETING, greeting_line: "Hi, Michael.", turn_detection: { silence_duration_ms: 1000, threshold: 0.5 } },
    stream: {}, api: "/api", WebSocketImpl: FakeWs, fetchImpl, player, AudioCtx: FakeAudioCtx,
  });
  const events = [];
  dc.onmessage = (ev) => events.push(JSON.parse(ev.data));
  const ws = FakeWs.last;
  const send = (e) => dc.send(JSON.stringify(e));
  return { dc, pc, ws, events, calls, send, player, types: () => events.map((e) => e.type) };
}

test("chosen only by ?aria_voice=cascade", () => {
  expect(requestedTransport("?aria_voice=cascade")).toBe("cascade");
  expect(requestedTransport("")).toBeNull();
  expect(requestedTransport("?aria_voice=other")).toBeNull();
});

test("sentences are spoken as soon as they are complete", () => {
  expect(takeSentences("Okay, Michael. I'll ask the nurse")).toEqual([["Okay, Michael."], "I'll ask the nurse"]);
  expect(takeSentences("Done! Anything else? ")).toEqual([["Done!", "Anything else?"], ""]);
  // a reply's first clause goes out at its comma; later commas wait for the sentence
  expect(takeSentences("I've let the nursing staff know, and they", true)).toEqual([["I've let the nursing staff know,"], "and they"]);
  expect(takeSentences("Okay, Michael", true)).toEqual([[], "Okay, Michael"]);
  expect(takeSentences("I've let the nursing staff know, and they", false)).toEqual([[], "I've let the nursing staff know, and they"]);
});

test("Realtime items map to chat messages", () => {
  expect(chatMessage({ type: "message", role: "user", content: [{ type: "input_text", text: "hi" }] })).toEqual({ role: "user", content: "hi" });
  expect(chatMessage({ type: "function_call_output", call_id: "c1", output: "{\"ok\":true}" })).toEqual({ role: "tool", tool_call_id: "c1", content: "{\"ok\":true}" });
  expect(chatMessage({ type: "message", role: "system", content: [{ text: "x" }] })).toBeNull();
});

test("opens like a data channel; the greeting is spoken locally with no model call", async () => {
  const t = setup();
  let opened = false;
  t.dc.onopen = () => { opened = true; };
  t.ws.serve({ type: "ready", sample_rate: 22050, gen: 0 });
  await flush();
  expect(opened).toBe(true);
  expect(t.ws.json()[0]).toEqual({ type: "config", silence_ms: 1000, threshold: 0.5 });
  expect(t.types()).toContain("session.created");
  expect(JSON.stringify(t.events)).not.toContain("tok_secret_value");
  t.send({ type: "response.create", response: GREETING });
  await flush();
  expect(t.calls.filter((c) => c.url.endsWith("/respond"))).toHaveLength(0);
  expect(t.ws.json().find((m) => m.type === "speak").text).toBe("Hi, Michael.");
  expect(t.types()).toEqual(expect.arrayContaining(["response.created", "response.output_audio_transcript.done", "response.done"]));
});

test("a spoken turn is transcribed, answered, and its tool call goes through the handler's own path", async () => {
  const t = setup({ replies: [
    () => sse([{ type: "text", delta: "Okay. " }, { type: "tool_call", id: "call_1", name: "create_care_request", arguments: "{\"category\":\"water\"}" }, { type: "done" }]),
    () => sse([{ type: "text", delta: "I've asked the nurse." }, { type: "done" }]),
  ] });
  t.ws.serve({ type: "ready", sample_rate: 22050, gen: 0 });
  t.ws.serve({ type: "speech_started" });
  t.ws.serve({ type: "speech_stopped", wav: btoa("RIFFfake") });
  await flush(); await flush();
  const transcribe = t.calls.find((c) => c.url.endsWith("/transcribe"));
  expect(transcribe.opts.headers["X-Aria-Voice-Token"]).toBe("tok_secret_value");
  expect(t.events.find((e) => e.type === "conversation.item.input_audio_transcription.completed").transcript).toBe("I need some water");
  const fn = t.events.find((e) => e.type === "response.function_call_arguments.done");
  expect(fn).toMatchObject({ call_id: "call_1", name: "create_care_request", arguments: "{\"category\":\"water\"}" });
  // what realtimeMessageHandler.js sends after running the tool
  t.send({ type: "conversation.item.create", item: { type: "function_call_output", call_id: "call_1", output: "{\"ok\":true}" } });
  t.send({ type: "response.create" });
  await flush(); await flush();
  const second = JSON.parse(t.calls.filter((c) => c.url.endsWith("/respond"))[1].opts.body);
  expect(second.items).toEqual([
    { role: "user", content: "I need some water" },
    { role: "assistant", content: "Okay.", tool_calls: [{ id: "call_1", type: "function", function: { name: "create_care_request", arguments: "{\"category\":\"water\"}" } }] },
    { role: "tool", tool_call_id: "call_1", content: "{\"ok\":true}" },
  ]);
  expect(t.ws.json().filter((m) => m.type === "speak").map((m) => m.text)).toEqual(["Okay.", "I've asked the nurse."]);
});

test("barge-in: speaking over Aria stops her at once and cancels the reply", async () => {
  let aborted = null;
  const t = setup({ replies: [(opts) => { aborted = opts.signal; return new Promise(() => {}); }] });
  t.ws.serve({ type: "ready", sample_rate: 22050, gen: 0 });
  t.send({ type: "response.create" });
  await flush();
  t.player.stop.mockReturnValue(true);
  t.ws.serve({ type: "speech_started" });
  await flush();
  expect(aborted.aborted).toBe(true);
  expect(t.ws.json().some((m) => m.type === "stop")).toBe(true);
  expect(t.types()).toEqual(expect.arrayContaining(["input_audio_buffer.speech_started", "output_audio_buffer.cleared"]));
  expect(t.events.find((e) => e.type === "response.done").response.status).toBe("cancelled");
  // audio of the interrupted reply that was already in flight is dropped
  const frame = new ArrayBuffer(8); new DataView(frame).setUint32(0, 0, true);
  t.ws.onmessage({ data: frame });
  expect(t.player.play).not.toHaveBeenCalled();
});

test("resting (create_response false) transcribes but does not answer; close ends the paid session", async () => {
  const t = setup();
  t.ws.serve({ type: "ready", sample_rate: 22050, gen: 0 });
  t.send({ type: "session.update", session: { type: "realtime", audio: { input: { turn_detection: { create_response: false } } } } });
  t.ws.serve({ type: "speech_stopped", wav: btoa("RIFFfake") });
  await flush(); await flush();
  expect(t.calls.filter((c) => c.url.endsWith("/respond"))).toHaveLength(0);
  t.dc.close();
  expect(t.calls.some((c) => c.url.endsWith("/aria-voice/end"))).toBe(true);
});

test("transcription starts at the first pause and is reused when the turn ends there", async () => {
  const t = setup();
  t.ws.serve({ type: "ready", sample_rate: 22050, gen: 0 });
  t.send({ type: "session.update", session: { audio: { input: { turn_detection: { create_response: false } } } } });
  t.ws.serve({ type: "speech_started" });
  t.ws.serve({ type: "speech_paused", wav: btoa("RIFFearly") });
  t.ws.serve({ type: "speech_stopped", wav: btoa("RIFFfull") });
  await flush(); await flush();
  expect(t.calls.filter((c) => c.url.endsWith("/transcribe"))).toHaveLength(1);
  expect(t.events.find((e) => e.type === "conversation.item.input_audio_transcription.completed").transcript).toBe("I need some water");
});

test("speaking on after a pause discards the early transcription", async () => {
  const t = setup();
  t.ws.serve({ type: "ready", sample_rate: 22050, gen: 0 });
  t.send({ type: "session.update", session: { audio: { input: { turn_detection: { create_response: false } } } } });
  t.ws.serve({ type: "speech_started" });
  t.ws.serve({ type: "speech_paused", wav: btoa("RIFFearly") });
  t.ws.serve({ type: "speech_resumed" });
  t.ws.serve({ type: "speech_stopped", wav: btoa("RIFFfull") });
  await flush(); await flush();
  const sent = t.calls.filter((c) => c.url.endsWith("/transcribe")).map((c) => new TextDecoder().decode(c.opts.body));
  expect(sent).toEqual(["RIFFearly", "RIFFfull"]);
});
