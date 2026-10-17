/** Turn ownership in the low-cost voice transport (cascadeTransport.js): every utterance owns its transcriptions
 * and its part in an interruption; results apply in spoken order; failures are not silence; stale reply events are
 * dropped. Transcriptions here are deferred promises, resolved in whatever order a test needs. */
import { TextEncoder, TextDecoder } from "util";
import { createCascadeConnection, createPlayer } from "../cascadeTransport";

global.TextEncoder = global.TextEncoder || TextEncoder;
global.TextDecoder = global.TextDecoder || TextDecoder;
const flush = async (n = 4) => { for (let i = 0; i < n; i++) await new Promise((r) => setTimeout(r, 2)); };

class FakeWs {
  constructor() { this.sent = []; this.readyState = 1; FakeWs.last = this; }
  send(m) { this.sent.push(m); }
  close() {}
  serve(obj) { this.onmessage({ data: JSON.stringify(obj) }); }
}
class FakeAudioCtx {
  constructor() { this.destination = {}; }
  createMediaStreamSource() { return { connect() {}, disconnect() {} }; }
  createScriptProcessor() { return { connect() {}, disconnect() {} }; }
  close() {}
}
const deferred = () => { let resolve, reject; const p = new Promise((a, b) => { resolve = a; reject = b; }); return { p, resolve, reject }; };
const ok = (text) => ({ ok: true, json: async () => ({ text }) });
const pcm = () => ({ ok: true, body: { getReader: () => { let sent = false;
  return { read: async () => (sent ? { done: true } : (sent = true, { value: new Uint8Array(4800), done: false })) }; } } });
/** An SSE body the test feeds one event at a time. */
function stream() {
  const q = [], waiters = [];
  const push = (v) => (waiters.length ? waiters.shift()(v) : q.push(v));
  return {
    res: { ok: true, body: { getReader: () => ({ read: () => (q.length ? Promise.resolve(q.shift()) : new Promise((r) => waiters.push(r))) }) } },
    event: (e) => push({ value: new TextEncoder().encode(`data: ${JSON.stringify(e)}\n\n`), done: false }),
    end: () => push({ done: true }),
  };
}

function harness() {
  const stt = [], replies = [], log = jest.fn();
  const fetchImpl = jest.fn((url, opts) => {
    if (url.endsWith("/transcribe")) { const d = deferred(); stt.push({ d, body: new TextDecoder().decode(opts.body) }); return d.p; }
    if (url.endsWith("/respond")) { const s = stream(); replies.push({ s, body: JSON.parse(opts.body) }); return Promise.resolve(s.res); }
    if (url.endsWith("/speak")) return Promise.resolve(pcm());
    return Promise.resolve({ ok: true, json: async () => ({}) });
  });
  let playing = false;
  const player = { get playing() { return playing; }, now: () => 0, ahead: () => 0, prepare: async () => null,
    play: jest.fn(() => { playing = true; return { start: 0, end: 5, gap: 0 }; }),
    stop: jest.fn(() => { const was = playing; playing = false; return was; }), hold: jest.fn(), duck: jest.fn(), close: jest.fn() };
  const { dc } = createCascadeConnection({ session: { token: "tok", audio_sample_rate: 24000, session: { model: "m" } },
    caos: { turn_detection: { silence_duration_ms: 1000, threshold: 0.5 } }, stream: {}, api: "/api",
    WebSocketImpl: FakeWs, fetchImpl, player, log, AudioCtx: FakeAudioCtx });
  const events = [];
  dc.onmessage = (ev) => events.push(JSON.parse(ev.data));
  const ws = FakeWs.last;
  ws.serve({ type: "ready" });
  const say = (wav, extra = {}) => ws.serve({ type: "speech_stopped", wav: btoa(wav), ...extra });
  const users = () => events.filter((e) => e.type === "conversation.item.input_audio_transcription.completed").map((e) => e.transcript);
  const receipts = (name) => log.mock.calls.filter(([n]) => n === name).map(([, d]) => d.meta);
  /** Starts a reply, streams one sentence and lets it become audible. */
  const speakingReply = async () => {
    dc.send(JSON.stringify({ type: "response.create" }));
    await flush();
    const r = replies[replies.length - 1];
    r.s.event({ type: "text", delta: "Here is a long answer about your day. " });
    await flush(8);
    return r;
  };
  return { ws, dc, stt, replies, log, player, events, say, users, receipts, speakingReply,
    types: () => events.map((e) => e.type) };
}

test("reversed transcription completion: words are kept in spoken order and answered once", async () => {
  const t = harness();
  t.ws.serve({ type: "speech_started" }); t.say("RIFFone");
  t.ws.serve({ type: "speech_started" }); t.say("RIFFtwo");
  await flush();
  expect(t.stt.map((s) => s.body)).toEqual(["RIFFone", "RIFFtwo"]);
  t.stt[1].d.resolve(ok("and the desk lamp too"));       // the newer one finishes first
  await flush();
  expect(t.users()).toEqual([]);                          // it waits for the older one
  t.stt[0].d.resolve(ok("turn the overhead light off"));
  await flush();
  expect(t.users()).toEqual(["turn the overhead light off", "and the desk lamp too"]);
  expect(t.replies).toHaveLength(1);
  expect(t.replies[0].body.items.filter((m) => m.role === "user").map((m) => m.content))
    .toEqual(["turn the overhead light off", "and the desk lamp too"]);
});

test("an older transcription finishing during newer speech never answers over it", async () => {
  const t = harness();
  t.ws.serve({ type: "speech_started" }); t.say("RIFFone");
  t.ws.serve({ type: "speech_started" });                 // Michael is still talking
  t.stt[0].d.resolve(ok("turn the light"));
  await flush();
  expect(t.users()).toEqual(["turn the light"]);
  expect(t.replies).toHaveLength(0);                      // no answer while he speaks
  t.say("RIFFtwo");
  t.stt[1].d.resolve(ok("off please"));
  await flush();
  expect(t.replies).toHaveLength(1);
  expect(t.replies[0].body.items.filter((m) => m.role === "user").map((m) => m.content)).toEqual(["turn the light", "off please"]);
});

test("newer speech that turns out empty still lets the older words be answered", async () => {
  const t = harness();
  t.ws.serve({ type: "speech_started" }); t.say("RIFFone");
  t.ws.serve({ type: "speech_started" });
  t.stt[0].d.resolve(ok("what's for dinner"));
  t.say("RIFFcough");
  t.stt[1].d.resolve(ok(""));                             // a successful empty result
  await flush();
  expect(t.replies).toHaveLength(1);
  expect(t.receipts("cascade_transcribe_failed")).toHaveLength(0);
});

test("speech over her voice pauses her at once; no words lets her carry on, and nothing is answered", async () => {
  const t = harness();
  await t.speakingReply();
  expect(t.types()).toContain("output_audio_buffer.started");
  t.ws.serve({ type: "speech_started" });
  expect(t.player.hold).toHaveBeenLastCalledWith(true);   // before any transcription
  expect(t.player.stop).not.toHaveBeenCalled();
  t.say("RIFFecho"); t.stt[0].d.resolve(ok(""));
  await flush();
  expect(t.player.hold).toHaveBeenLastCalledWith(false);
  expect(t.player.stop).not.toHaveBeenCalled();
  expect(t.receipts("cascade_barge_in")).toEqual([expect.objectContaining({ outcome: "ignored", words: 0, was_playing: true })]);
  expect(t.replies).toHaveLength(1);
});

test("words at the speaker's first pause stop her without waiting for the turn to end", async () => {
  const t = harness();
  await t.speakingReply();
  t.ws.serve({ type: "speech_started" });
  t.ws.serve({ type: "speech_paused", wav: btoa("RIFFearly") });
  t.stt[0].d.resolve(ok("wait stop"));
  await flush();
  expect(t.player.stop).toHaveBeenCalled();
  expect(t.types()).toContain("output_audio_buffer.cleared");
  expect(t.receipts("cascade_barge_in")).toEqual([expect.objectContaining({ outcome: "stopped", confirmed_by: "early", words: 2 })]);
});

test("overlapping interruptions share one check: the second speaker's words stop her, once", async () => {
  const t = harness();
  await t.speakingReply();
  t.ws.serve({ type: "speech_started" }); t.say("RIFFbump");
  t.ws.serve({ type: "speech_started" });                 // more sound before the first is judged
  t.stt[0].d.resolve(ok(""));
  await flush();
  expect(t.player.hold).toHaveBeenLastCalledWith(true);   // still paused: the second is not judged yet
  t.say("RIFFwords"); t.stt[1].d.resolve(ok("hold on"));
  await flush();
  expect(t.player.stop).toHaveBeenCalledTimes(1);
  expect(t.receipts("cascade_barge_in")).toHaveLength(1);
  expect(t.users()).toEqual(["", "hold on"]);
  expect(t.replies).toHaveLength(2);                      // his words are answered
});

test("a failed transcription is not silence: she stays stopped and the failure is receipted", async () => {
  const t = harness();
  await t.speakingReply();
  t.ws.serve({ type: "speech_started" }); t.say("RIFFx");
  t.stt[0].d.resolve({ ok: false, status: 502, json: async () => ({}) });
  await flush();
  expect(t.player.stop).toHaveBeenCalled();
  expect(t.receipts("cascade_barge_in")).toEqual([expect.objectContaining({ outcome: "stopped", confirmed_by: "final_failed" })]);
  expect(t.receipts("cascade_transcribe_failed")).toEqual([{ transport: "cascade", stage: "final", reason: "http_error", status: 502 }]);
  expect(t.types()).toContain("conversation.item.input_audio_transcription.failed");
  expect(t.users()).toEqual([]);                          // never reported as an empty (silent) turn
});

test("network and malformed replies are failures too, never empty speech", async () => {
  const t = harness();
  t.ws.serve({ type: "speech_started" }); t.say("RIFFa");
  t.ws.serve({ type: "speech_started" }); t.say("RIFFb");
  t.stt[0].d.reject(new Error("offline"));
  t.stt[1].d.resolve({ ok: true, json: async () => { throw new SyntaxError("x"); } });
  await flush();
  expect(t.receipts("cascade_transcribe_failed").map((m) => m.reason)).toEqual(["network", "bad_json"]);
  expect(t.users()).toEqual([]);
  expect(t.replies).toHaveLength(0);
});

test("speech after the pause: the early transcript is discarded and the whole turn is transcribed", async () => {
  const t = harness();
  t.ws.serve({ type: "speech_started" });
  t.ws.serve({ type: "speech_paused", wav: btoa("RIFFearly") });
  t.say("RIFFfull", { early_ok: false });               // the service heard more after the pause
  t.stt[0].d.resolve(ok("can you"));
  await flush();
  expect(t.stt.map((s) => s.body)).toEqual(["RIFFearly", "RIFFfull"]);
  t.stt[1].d.resolve(ok("can you turn the TV back on"));
  await flush();
  expect(t.users()).toEqual(["can you turn the TV back on"]);
});

test("an early transcription that failed is replaced by the full turn's", async () => {
  const t = harness();
  t.ws.serve({ type: "speech_started" });
  t.ws.serve({ type: "speech_paused", wav: btoa("RIFFearly") });
  t.say("RIFFfull", { early_ok: true });
  t.stt[0].d.resolve({ ok: false, status: 500, json: async () => ({}) });
  await flush();
  expect(t.stt.map((s) => s.body)).toEqual(["RIFFearly", "RIFFfull"]);
  t.stt[1].d.resolve(ok("lights off"));
  await flush();
  expect(t.users()).toEqual(["lights off"]);
  expect(t.receipts("cascade_transcribe_failed")).toEqual([expect.objectContaining({ stage: "early", status: 500 })]);
  expect(t.replies).toHaveLength(1);
});

test("a cancelled reply's late text and tool calls are dropped", async () => {
  const t = harness();
  t.dc.send(JSON.stringify({ type: "response.create" }));
  await flush();
  const r = t.replies[0];
  r.s.event({ type: "text", delta: "Let me" });
  await flush();
  t.ws.serve({ type: "speech_started" });                 // not yet audible: she stops at once
  await flush();
  r.s.event({ type: "text", delta: " turn that off. " });
  r.s.event({ type: "tool_call", id: "c1", name: "toggle_light", arguments: "{}" });
  r.s.end();
  await flush(8);
  const id = t.events.find((e) => e.type === "response.created").response.id;
  const late = t.events.filter((e) => e.response_id === id && /delta|function_call/.test(e.type));
  expect(late.map((e) => e.delta || e.type)).toEqual(["Let me"]);
  expect(t.events.filter((e) => e.type === "response.done" && e.response.id === id).map((e) => e.response.status)).toEqual(["cancelled"]);
});

test("the goodbye's metadata comes back on its response events", async () => {
  const t = harness();
  t.dc.send(JSON.stringify({ type: "response.create", response: { instructions: "x", metadata: { caos_goodbye: "1" } } }));
  await flush();
  expect(t.events.find((e) => e.type === "response.created").response.metadata).toEqual({ caos_goodbye: "1" });
});

test("the player pauses on the audio clock and resumes; stopping always resumes the clock", async () => {
  const calls = [];
  function Ctx() {
    this.currentTime = 0; this.destination = {};
    this.suspend = () => { calls.push("suspend"); return Promise.resolve(); };
    this.resume = () => { calls.push("resume"); return Promise.resolve(); };
    this.createBuffer = (c, n, rate) => ({ duration: n / rate, copyToChannel() {} });
    this.createBufferSource = () => ({ connect() {}, start() {}, stop() {} });
    this.createGain = () => ({ gain: { value: 1, setTargetAtTime(v) { this.value = v; } }, connect() {} });
    this.close = () => {};
  }
  const p = createPlayer({ AudioCtx: Ctx });
  await p.prepare();
  p.play(new Int16Array(2400), 24000);
  p.hold(true); p.hold(true);
  p.hold(false);
  p.hold(true);
  p.stop();
  expect(calls).toEqual(["suspend", "resume", "suspend", "resume"]);
});

// --- startup: the greeting window (create_response off until the greeting's audio stops) ---
const gate = (t, on) => t.dc.send(JSON.stringify({ type: "session.update",
  session: { audio: { input: { turn_detection: { create_response: on } } } } }));
const greet = async (t) => {
  gate(t, false);
  t.dc.send(JSON.stringify({ type: "response.create", response: { instructions: "greet" } }));
  await flush();
  const r = t.replies[t.replies.length - 1];
  r.s.event({ type: "text", delta: "Hey, Michael. " }); r.s.end();
  await flush(8);
  return r;
};

test("an immediate first reply after the greeting is kept and answered exactly once", async () => {
  const t = harness();
  await greet(t);
  t.player.stop(); gate(t, true);                         // greeting audio over: the gate re-enables replies
  t.ws.serve({ type: "speech_started" }); t.say("RIFFquick");
  t.stt[0].d.resolve(ok("that was quick"));
  await flush();
  expect(t.users()).toEqual(["that was quick"]);
  expect(t.replies).toHaveLength(2);                      // greeting + one answer
});

test("words over the greeting stop it and are answered once the greeting window closes", async () => {
  const t = harness();
  await greet(t);
  t.ws.serve({ type: "speech_started" });                 // over the greeting's audio
  t.say("RIFFquick"); t.stt[0].d.resolve(ok("that was quick"));
  await flush();
  expect(t.users()).toEqual(["that was quick"]);
  expect(t.player.stop).toHaveBeenCalled();
  expect(t.replies).toHaveLength(1);                      // no reply while the window is closed
  gate(t, true);                                          // the gate re-enables after the cleared greeting
  await flush();
  expect(t.replies).toHaveLength(2);                      // answered - once
  gate(t, true);
  await flush();
  expect(t.replies).toHaveLength(2);
  expect(t.replies[1].body.items.filter((m) => m.role === "user").map((m) => m.content)).toEqual(["that was quick"]);
});

test("a reply still being spoken when the window reopens is answered when it ends, once", async () => {
  const t = harness();
  await greet(t);
  t.ws.serve({ type: "speech_started" });
  t.say("RIFFa"); t.stt[0].d.resolve(ok("that was quick"));
  t.ws.serve({ type: "speech_started" });                 // he keeps talking
  await flush();
  gate(t, true);
  await flush();
  expect(t.replies).toHaveLength(1);                      // not over his speech
  t.say("RIFFb"); t.stt[1].d.resolve(ok("can you hear me"));
  await flush();
  expect(t.replies).toHaveLength(2);
  expect(t.replies[1].body.items.filter((m) => m.role === "user").map((m) => m.content)).toEqual(["that was quick", "can you hear me"]);
});

test("delayed voice-service start: nothing opens or plays before it is ready, and the first turn is answered once", async () => {
  const stt = [], replies = [];
  const fetchImpl = jest.fn((url, opts) => {
    if (url.endsWith("/transcribe")) { const d = deferred(); stt.push(d); return d.p; }
    if (url.endsWith("/respond")) { const s = stream(); replies.push(s); return Promise.resolve(s.res); }
    return Promise.resolve(pcm());
  });
  const player = { playing: false, now: () => 0, ahead: () => 0, prepare: jest.fn(async () => null),
    play: jest.fn(() => ({ start: 0, end: 1, gap: 0 })), stop: jest.fn(() => false), hold: jest.fn(), close: jest.fn() };
  const { dc } = createCascadeConnection({ session: { token: "tok", session: { model: "m" } },
    caos: { turn_detection: { silence_duration_ms: 1000, threshold: 0.5 } }, stream: {}, api: "/api",
    WebSocketImpl: FakeWs, fetchImpl, player, AudioCtx: FakeAudioCtx });
  const opened = jest.fn();
  dc.onopen = opened;
  await flush();
  expect(dc.readyState).toBe("connecting");                // the room handler greets only on open
  expect(opened).not.toHaveBeenCalled();
  expect(player.prepare).not.toHaveBeenCalled();
  const ws = FakeWs.last;
  ws.serve({ type: "ready" });                            // service ready: config + microphone + output
  await flush();
  expect(JSON.parse(ws.sent[0]).type).toBe("config");
  expect(player.prepare).toHaveBeenCalled();
  expect(opened).toHaveBeenCalledTimes(1);
  ws.serve({ type: "speech_started" }); ws.serve({ type: "speech_stopped", wav: btoa("RIFFx") });
  stt[0].resolve(ok("hello"));
  await flush();
  expect(replies).toHaveLength(1);
});

test("words while she rests are kept but not answered when replies come back on; new words are", async () => {
  const t = harness();
  gate(t, false);                                         // resting: replies off, nothing in progress
  t.ws.serve({ type: "speech_started" }); t.say("RIFFtv"); t.stt[0].d.resolve(ok("the weather tomorrow"));
  await flush();
  gate(t, true);                                          // she wakes
  await flush();
  expect(t.replies).toHaveLength(0);
  t.ws.serve({ type: "speech_started" }); t.say("RIFFhi"); t.stt[1].d.resolve(ok("Aria, are you there"));
  await flush();
  expect(t.replies).toHaveLength(1);
});
