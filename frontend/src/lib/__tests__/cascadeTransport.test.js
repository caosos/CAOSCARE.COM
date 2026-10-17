/** Low-cost voice transport (cascadeTransport.js): emits the Realtime events the room handler already uses. */
import { TextEncoder, TextDecoder } from "util";
import { chatMessage, createCascadeConnection, requestItems, takeSentences } from "../cascadeTransport";
import { urlTransport } from "../useVoiceTransport";
import { GOODBYE_INSTRUCTIONS, GOODBYE_LINE } from "../endController";

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

const pcm = (n = 480) => ({ ok: true, body: { getReader: () => { let sent = false;
  return { read: async () => (sent ? { done: true } : (sent = true, { value: new Uint8Array(n * 2), done: false })) }; } } });

function setup({ replies = [], transcript = "I need some water", speakImpl = () => pcm(), extra = {} } = {}) {
  const calls = [];
  const fetchImpl = jest.fn(async (url, opts) => {
    calls.push({ url, opts });
    if (url.endsWith("/transcribe")) return { ok: true, json: async () => ({ text: transcript }) };
    if (url.endsWith("/respond")) return replies.length ? replies.shift()(opts) : sse([{ type: "done" }]);
    if (url.endsWith("/speak")) return speakImpl(opts);
    return { ok: true, json: async () => ({ ok: true }) };
  });
  const player = { playing: false, now: () => 0, ahead: () => 0, prepare: async () => null,
    play: jest.fn(() => ({ start: 0, end: 0.02, gap: 0 })), stop: jest.fn(() => false), close: jest.fn() };
  const spoken = () => calls.filter((c) => c.url.endsWith("/speak")).map((c) => JSON.parse(c.opts.body).text);
  const { dc, pc } = createCascadeConnection({
    session: { token: "tok_secret_value", audio_sample_rate: 24000, session: { model: "gpt-4o-mini" } },
    caos: { greeting: GREETING, greeting_line: "Hi, Michael.", turn_detection: { silence_duration_ms: 1000, threshold: 0.5 } },
    stream: {}, api: "/api", WebSocketImpl: FakeWs, fetchImpl, player, AudioCtx: FakeAudioCtx, ...extra,
  });
  const events = [];
  dc.onmessage = (ev) => events.push(JSON.parse(ev.data));
  const ws = FakeWs.last;
  const send = (e) => dc.send(JSON.stringify(e));
  return { dc, pc, ws, events, calls, send, player, spoken, types: () => events.map((e) => e.type) };
}

test("a test URL can override the room's setting; anything else leaves it to the kiosk record", () => {
  expect(urlTransport("?aria_voice=cascade")).toBe("cascade");
  expect(urlTransport("?aria_voice=realtime")).toBe("realtime");
  expect(urlTransport("?aria_voice=other")).toBeNull();
  expect(urlTransport("")).toBeNull();
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

test("opens like a data channel; the greeting needs no reasoning call", async () => {
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
  expect(t.spoken()).toEqual(["Hi, Michael."]);
  expect(JSON.parse(t.calls.find((c) => c.url.endsWith("/speak")).opts.body).fixed).toBe(true);   // cached line
  expect(t.calls.find((c) => c.url.endsWith("/speak")).opts.headers["X-Aria-Voice-Token"]).toBe("tok_secret_value");
  expect(t.player.play).toHaveBeenCalledWith(expect.any(Int16Array), 24000);
  expect(t.types()).toContain("output_audio_buffer.started");
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
  expect(t.spoken()).toEqual(["Okay.", "I've asked the nurse."]);
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
  expect(t.types()).toEqual(expect.arrayContaining(["input_audio_buffer.speech_started", "output_audio_buffer.cleared"]));
  expect(t.events.find((e) => e.type === "response.done").response.status).toBe("cancelled");
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
  t.ws.serve({ type: "speech_stopped", wav: btoa("RIFFfull"), early_ok: true });
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

test("interrupted mid-reply: only the sentences that reached the speaker stay in the conversation", async () => {
  let speakAbort = null;
  const t = setup({
    replies: [() => sse([{ type: "text", delta: "First I'll tell you this. " }, { type: "text", delta: "Then a long second part. " }, { type: "done" }]),
      () => sse([{ type: "done" }])],
    speakImpl: (opts) => (JSON.parse(opts.body).text.startsWith("First") ? pcm() : (speakAbort = opts.signal, new Promise(() => {}))),
  });
  t.ws.serve({ type: "ready", sample_rate: 24000 });
  t.send({ type: "response.create" });
  await flush(); await flush();
  t.player.playing = true; t.player.stop.mockReturnValue(true);
  t.player.now = () => 1;                                // the first sentence has played to its end
  t.ws.serve({ type: "speech_started" });                // while she is audible, words decide
  t.ws.serve({ type: "speech_stopped", wav: btoa("RIFFfake") });
  await flush(); await flush();
  expect(speakAbort.aborted).toBe(true);                 // the unplayed sentence's audio request is cancelled
  const items = JSON.parse(t.calls.filter((c) => c.url.endsWith("/respond"))[1].opts.body).items;
  expect(items).toEqual([{ role: "assistant", content: "First I'll tell you this." }, { role: "user", content: "I need some water" }]);
});

test("the routine goodbye is a fixed line: no reasoning call, spoken at once in Aria's voice", async () => {
  const t = setup();
  t.ws.serve({ type: "ready" });
  t.send({ type: "response.create", response: { instructions: GOODBYE_INSTRUCTIONS } });
  await flush(); await flush();
  expect(t.calls.filter((c) => c.url.endsWith("/respond"))).toHaveLength(0);
  expect(t.spoken()).toEqual([GOODBYE_LINE]);
  expect(t.types()).toEqual(expect.arrayContaining(["output_audio_buffer.started", "response.output_audio_transcript.done"]));
});

test("a reply asked for while a tool call is unanswered still sends a valid conversation", () => {
  const call = (id) => ({ id, type: "function", function: { name: "end_call", arguments: "{}" } });
  expect(requestItems([
    { role: "user", content: "That's all." },
    { role: "assistant", content: "Okay.", tool_calls: [call("c1")] },          // no result yet
    { role: "assistant", content: null, tool_calls: [call("c2")] },            // no result, no words
    { role: "tool", tool_call_id: "c9", content: "{}" },                       // result for no call
    { role: "assistant", content: null, tool_calls: [call("c3")] },
    { role: "tool", tool_call_id: "c3", content: "{\"ok\":true}" },
  ])).toEqual([
    { role: "user", content: "That's all." },
    { role: "assistant", content: "Okay." },
    { role: "assistant", content: null, tool_calls: [call("c3")] },
    { role: "tool", tool_call_id: "c3", content: "{\"ok\":true}" },
  ]);
});

test("Aria's voice plays through a WebRTC loopback into the page's audio element, so echo cancellation removes it", async () => {
  const { createPlayer } = require("../cascadeTransport");
  const tracks = [{ kind: "audio" }];
  const ctx = { currentTime: 0, destination: "speakers",
    createMediaStreamDestination: () => ({ stream: { getTracks: () => tracks } }),
    createBuffer: () => ({ duration: 0.02, copyToChannel() {} }),
    createBufferSource: () => ({ connect: jest.fn(), start: jest.fn(), stop() {} }), close() {} };
  const peers = [];
  class FakeRTC {
    constructor() { peers.push(this); this.added = []; this.connectionState = "connected"; }
    addTrack(t) { this.added.push(t); }
    async createOffer() { return { type: "offer", sdp: "o" }; }
    async createAnswer() { return { type: "answer", sdp: "a" }; }
    async setLocalDescription(d) { this.localDescription = d; }
    async setRemoteDescription(d) { this.remoteDescription = d; if (d.type === "offer") setTimeout(() => this.ontrack?.({ streams: ["loopback-stream"] }), 0); }
    close() {}
  }
  const audioEl = { play: jest.fn(() => Promise.resolve()) };
  const player = createPlayer({ AudioCtx: function () { return ctx; }, audioEl, RTC: FakeRTC });
  await player.prepare();
  await new Promise((r) => setTimeout(r, 5));
  expect(peers).toHaveLength(2);
  expect(peers[0].added).toEqual(tracks);                 // her audio goes into the peer connection...
  expect(audioEl.srcObject).toBe("loopback-stream");      // ...and is played by the page's audio element
  expect(audioEl.play).toHaveBeenCalled();
});

const DIAG = { kind: "energy_segment", start_epoch_ms: 1, duration_s: 1.2, peak_dbfs: -9, mean_dbfs: -28,
  vad_speech_frames: 0, vad_turn_started: false, no_speech_detected: true };

test("detector diagnostics: asked for and logged only on a measured page", async () => {
  const log = jest.fn();
  const { ws } = setup({ extra: { log } });
  ws.serve({ type: "ready" });
  expect(ws.json()[0]).toEqual({ type: "config", silence_ms: 1000, threshold: 0.5 });   // nothing asked
  ws.serve({ type: "diag", data: DIAG });                                                // an old/odd service
  expect(log.mock.calls.filter(([t]) => t === "cascade_vad_diag")).toHaveLength(0);

  const log2 = jest.fn();
  const b = setup({ extra: { log: log2, diagnostics: true } });
  b.ws.serve({ type: "ready" });
  expect(b.ws.json()[0]).toMatchObject({ type: "config", diagnostics: true, threshold: 0.5, silence_ms: 1000 });
  b.ws.serve({ type: "diag", data: DIAG });
  expect(log2).toHaveBeenCalledWith("cascade_vad_diag", { meta: { transport: "cascade", ...DIAG } });
});

test("a failing diagnostic log never affects the call", async () => {
  const log = jest.fn((t) => { if (t === "cascade_vad_diag") throw new Error("diagnostics down"); });
  const rejecting = jest.fn((t) => (t === "cascade_vad_diag" ? Promise.reject(new Error("offline")) : undefined));
  for (const l of [log, rejecting]) {
    const { ws, types } = setup({ extra: { log: l, diagnostics: true } });
    ws.serve({ type: "ready" });
    expect(() => ws.serve({ type: "diag", data: DIAG })).not.toThrow();
    ws.serve({ type: "speech_started" });
    await flush();
    expect(types()).toContain("input_audio_buffer.speech_started");
  }
});
