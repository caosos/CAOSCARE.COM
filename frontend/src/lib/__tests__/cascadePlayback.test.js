/** Low-cost voice playback (cascadeTransport.js) on a controlled audio clock: delayed, short, failed and interrupted
 * speech. Synthetic PCM and mock providers only - no network, no credentials, no microphone. */
import { TextEncoder, TextDecoder } from "util";
import { createCascadeConnection, createPlayer } from "../cascadeTransport";

global.TextEncoder = global.TextEncoder || TextEncoder;
global.TextDecoder = global.TextDecoder || TextDecoder;
const flush = () => new Promise((r) => setTimeout(r, 5));
const RATE = 24000;

/** A Web Audio context whose clock only moves when the test moves it. */
function clockCtx() {
  const ctx = { currentTime: 0, destination: { name: "speakers" }, sources: [],
    createMediaStreamDestination: () => ({ name: "loopback", stream: { getTracks: () => [{ kind: "audio" }] } }),
    createBuffer: (_c, length, rate) => ({ length, duration: length / rate, copyToChannel() {} }),
    createBufferSource() {
      const s = { connect(n) { s.node = n; s.connectedAt = ctx.currentTime; }, start(t) { s.at = Math.max(t, ctx.currentTime); },
        stop() { s.stoppedAt = ctx.currentTime; } };
      ctx.sources.push(s); return s;
    },
    close() {},
    advance(dt) {
      ctx.currentTime += dt;
      ctx.sources.filter((s) => s.at != null && !s.done && s.stoppedAt == null && s.at + s.buffer.duration <= ctx.currentTime + 1e-9)
        .forEach((s) => { s.done = true; s.onended?.(); });
    },
    // seconds of scheduled audio that were never routed anywhere (started before being connected)
    lost: () => ctx.sources.reduce((n, s) => n + (s.at == null ? 0 : Math.max(0, Math.min(s.connectedAt ?? Infinity, s.at + s.buffer.duration) - s.at)), 0),
    // silent holes between consecutive pieces of audio
    gaps() { const p = ctx.sources.filter((s) => s.at != null).sort((a, b) => a.at - b.at); const g = [];
      for (let i = 1; i < p.length; i++) { const d = p[i].at - (p[i - 1].at + p[i - 1].buffer.duration); if (d > 1e-6) g.push(d); } return g; },
    samples: () => ctx.sources.reduce((n, s) => n + s.buffer.length, 0),
  };
  return ctx;
}

/** A /speak response whose body the test feeds chunk by chunk. */
function speechStream() {
  const q = []; let wait = null, ended = false, failed = null;
  const take = () => { if (q.length) return Promise.resolve({ value: q.shift(), done: false });
    if (failed) return Promise.reject(failed); if (ended) return Promise.resolve({ done: true });
    return new Promise((ok, no) => { wait = { ok, no }; }); };
  const kick = () => { if (!wait) return; const w = wait; wait = null; take().then(w.ok, w.no); };
  return { res: { ok: true, body: { getReader: () => ({ read: take, cancel() { ended = true; kick(); } }) } },
    push(bytes) { q.push(bytes); kick(); }, end() { ended = true; kick(); }, fail(e) { failed = e; kick(); } };
}
const ms = (n) => new Uint8Array(Math.round(RATE * n / 1000) * 2);   // n ms of PCM16 silence

function setup({ reply = ["Hello there. ", "How are you today? "], speak, ctx = clockCtx(), rtc = null } = {}) {
  const streams = [], logs = [], events = [];
  const fetchImpl = jest.fn(async (url, opts) => {
    if (url.endsWith("/respond")) {
      const chunks = [...reply.map((d) => ({ type: "text", delta: d })), { type: "done" }].map((e) => new TextEncoder().encode(`data: ${JSON.stringify(e)}\n\n`));
      return { ok: true, body: { getReader: () => ({ read: async () => (chunks.length ? { value: chunks.shift(), done: false } : { done: true }) }) } };
    }
    if (url.endsWith("/speak")) {
      if (speak) return speak(JSON.parse(opts.body).text, opts);
      const s = speechStream(); s.signal = opts.signal; s.text = JSON.parse(opts.body).text; streams.push(s); return s.res;
    }
    if (url.endsWith("/transcribe")) return { ok: true, json: async () => ({ text: setup.transcript ?? "" }) };
    return { ok: true, json: async () => ({}) };
  });
  const player = createPlayer({ AudioCtx: function () { return ctx; }, audioEl: rtc ? {} : null, RTC: rtc });
  class Ws { constructor() { Ws.last = this; this.readyState = 1; } send() {} close() {} }
  const { dc } = createCascadeConnection({ session: { token: "t", audio_sample_rate: RATE, session: {} }, caos: {}, stream: {},
    api: "/api", WebSocketImpl: Ws, fetchImpl, player, AudioCtx: function () { return { createMediaStreamSource: () => ({ connect() {} }), createScriptProcessor: () => ({ connect() {} }) }; },
    log: (type, d) => logs.push({ type, ...d }) });
  dc.onmessage = (ev) => events.push(JSON.parse(ev.data));
  const serve = (m) => Ws.last.onmessage({ data: JSON.stringify(m) });
  serve({ type: "ready" });
  return { ctx, streams, logs, events, serve, dc, fetchImpl, send: (e) => dc.send(JSON.stringify(e)) };
}
const nextItems = (t) => JSON.parse(t.fetchImpl.mock.calls.filter(([u]) => u.endsWith("/respond")).pop()[1].body).items;

test("delayed audio is buffered, not stuttered: one rebuffer, every sample kept", async () => {
  const t = setup({ reply: ["Hello there. "] });
  t.send({ type: "response.create" });
  await flush();
  const s = t.streams[0];
  for (let i = 0; i < 20; i++) { s.push(ms(20)); await flush(); t.ctx.advance(0.03); }   // 20 ms of audio every 30 ms
  s.end(); await flush();
  t.ctx.advance(5); await flush();
  expect(t.ctx.samples()).toBe(20 * 480);                     // nothing dropped to catch up
  expect(t.ctx.gaps().length).toBeLessThanOrEqual(2);         // a few rebuffers, not a hole after every chunk
  const r = t.logs.find((l) => l.type === "cascade_playback").meta;
  expect(r.underruns).toBe(t.ctx.gaps().length);              // and each one is counted
  expect(r.outcome).toBe("completed");
});

test("nothing plays before the echo-cancelled output is connected (no lost start of the greeting)", async () => {
  let connect;
  class SlowRTC {
    constructor() { this.connectionState = "new"; SlowRTC.peers = [...(SlowRTC.peers || []), this]; connect = () => SlowRTC.peers.forEach((p) => { p.connectionState = "connected"; p.onconnectionstatechange?.(); }); }
    addTrack() {} async createOffer() { return { type: "offer" }; } async createAnswer() { return { type: "answer" }; }
    async setLocalDescription(d) { this.localDescription = d; } async setRemoteDescription(d) { if (d.type === "offer") setTimeout(() => this.ontrack?.({ streams: ["s"] }), 0); }
    close() {}
  }
  const t = setup({ reply: ["Hello there. "], rtc: SlowRTC });
  t.send({ type: "response.create" });
  await flush();
  t.streams[0].push(ms(400)); t.streams[0].end(); await flush();
  t.ctx.advance(0.3); const up = t.ctx.currentTime; connect(); await flush(); await flush();   // the loopback carries media from 300 ms
  t.ctx.advance(2); await flush();
  expect(t.ctx.samples()).toBe(400 * 24);
  const lost = t.ctx.sources.reduce((n, s) => n + Math.max(0, Math.min(up, s.at + s.buffer.duration) - s.at), 0);
  expect(lost).toBe(0);
  expect(t.ctx.sources.every((s) => s.node?.name === "loopback")).toBe(true);
});

test("failed, empty and unreachable speech is reported, never silently skipped", async () => {
  const outcomes = { "One.": { ok: false, status: 502 }, "Two.": "empty", "Three.": "reject" };
  const t = setup({ reply: ["One. ", "Two. ", "Three. "], speak: async (text) => {
    const o = outcomes[text];
    if (o === "reject") throw new TypeError("Failed to fetch");
    if (o === "empty") return { ok: true, body: { getReader: () => ({ read: async () => ({ done: true }) }) } };
    return o;
  } });
  t.send({ type: "response.create" });
  await flush(); await flush(); await flush();
  const failed = t.logs.filter((l) => l.type === "cascade_speech_failed").map((l) => l.meta);
  expect(failed).toHaveLength(3);
  expect(failed).toEqual(expect.arrayContaining([
    expect.objectContaining({ reason: "http_error", status: 502, chars: 4 }),
    expect.objectContaining({ reason: "empty", chars: 4 }),
    expect.objectContaining({ reason: "network", chars: 6 }),
  ]));
  expect(JSON.stringify(t.logs)).not.toMatch(/One\.|Two\.|Three\./);   // metadata only
  const r = t.logs.find((l) => l.type === "cascade_playback").meta;
  expect(r).toMatchObject({ failed: 3, sentences: 3, sentences_heard: 0 });
  // nothing was heard, so nothing is recorded as said
  t.send({ type: "response.create" }); await flush(); await flush();
  expect(nextItems(t)).toEqual([]);
});

test("a sentence queued but not yet played is not counted as heard when Aria is interrupted", async () => {
  const t = setup();
  t.send({ type: "response.create" });
  await flush(); await flush();
  t.streams[0].push(ms(600)); t.streams[0].end();
  t.streams[1].push(ms(600)); t.streams[1].end();
  await flush();
  t.ctx.advance(0.7); await flush();          // first sentence fully played, second just started
  t.serve({ type: "speech_started" });
  await flush();
  const r = t.logs.find((l) => l.type === "cascade_playback").meta;
  expect(r).toMatchObject({ outcome: "cancelled", reason: "turn_detected", sentences_heard: 1 });
  expect(r.partial_ms).toBeGreaterThan(0);
  t.send({ type: "response.create" }); await flush(); await flush();
  expect(nextItems(t)).toEqual([{ role: "assistant", content: "Hello there." }]);
});

test("interruption flushes at once and rejects late chunks of the cancelled speech", async () => {
  const t = setup({ reply: ["Hello there. "] });
  t.send({ type: "response.create" });
  await flush();
  t.streams[0].push(ms(300)); await flush();
  t.ctx.advance(0.1);
  t.serve({ type: "speech_started" });
  expect(t.streams[0].signal.aborted).toBe(true);
  const scheduled = t.ctx.sources.length;
  expect(t.ctx.sources.every((s) => s.stoppedAt != null || s.done)).toBe(true);   // all sound stopped
  t.streams[0].push(ms(300)); await flush();                                       // a provider that ignores the abort
  expect(t.ctx.sources.length).toBe(scheduled);
  const f = t.logs.find((l) => l.type === "cascade_speech_failed").meta;
  expect(f).toMatchObject({ reason: "interrupted" });
  expect(f.late_chunks).toBeGreaterThanOrEqual(1);
});

test("odd-sized network chunks split no samples", async () => {
  const t = setup({ reply: ["Hello there. "] });
  t.send({ type: "response.create" });
  await flush();
  const whole = ms(100);
  for (const [a, b] of [[0, 1], [1, 2001], [2001, 2002], [2002, whole.length]]) { t.streams[0].push(whole.slice(a, b)); await flush(); }
  t.streams[0].end(); await flush();
  t.ctx.advance(1); await flush();
  expect(t.ctx.samples()).toBe(whole.length / 2);
});

test("receipts carry timing, depth and outcome but no words", async () => {
  const t = setup();
  t.send({ type: "response.create" });
  await flush(); await flush();
  t.streams.forEach((s) => { s.push(ms(200)); s.end(); });
  await flush(); t.ctx.advance(1); await flush();
  const r = t.logs.find((l) => l.type === "cascade_playback");
  expect(r.meta).toMatchObject({ outcome: "completed", sentences: 2, sentences_heard: 2, failed: 0, underruns: 0 });
  expect(r.meta.max_queue_depth).toBeGreaterThanOrEqual(1);
  expect(typeof r.meta.first_audio_ms).toBe("number");
  expect(JSON.stringify(r)).not.toMatch(/Hello|How are you/);
});

test("lead 4 (kept): any detected speech interrupts her; an interruption with no words is recorded", async () => {
  setup.transcript = "";
  const t = setup({ reply: ["Hello there. "] });
  t.send({ type: "response.create" });
  await flush();
  t.streams[0].push(ms(600)); await flush();
  t.ctx.advance(0.2);
  t.serve({ type: "speech_started" });                       // e.g. her own echo
  t.serve({ type: "speech_stopped", wav: btoa("RIFF") });
  await flush(); await flush();
  expect(t.events.map((e) => e.type)).toContain("output_audio_buffer.cleared");   // she stopped mid-sentence
  expect(t.logs.find((l) => l.type === "cascade_barge_in").meta).toMatchObject({ words: 0 });
  setup.transcript = undefined;
});
