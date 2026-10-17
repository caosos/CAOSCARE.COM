/** Latency and startup measurement in the low-cost voice transport (metadata only), and the end-of-stream behaviour it
 * measures. No provider is called: replies and speech are deferred fakes. */
import { TextEncoder, TextDecoder } from "util";
import { createCascadeConnection } from "../cascadeTransport";

global.TextEncoder = global.TextEncoder || TextEncoder;
global.TextDecoder = global.TextDecoder || TextDecoder;
const flush = async (n = 6) => { for (let i = 0; i < n; i++) await new Promise((r) => setTimeout(r, 2)); };

class FakeWs { constructor() { this.sent = []; this.readyState = 1; FakeWs.last = this; } send(m) { this.sent.push(m); } close() {}
  serve(o) { this.onmessage({ data: JSON.stringify(o) }); } }
const procs = [];
class Ctx {
  constructor() { this.destination = {}; this.state = "running"; }
  createMediaStreamSource() { return { connect() {}, disconnect() {} }; }
  createScriptProcessor() { const p = { connect() {}, disconnect() {} }; procs.push(p); return p; }
  close() {}
}
function stream() {
  const q = [], w = [];
  const push = (v) => (w.length ? w.shift()(v) : q.push(v));
  return { res: { ok: true, body: { getReader: () => ({ read: () => (q.length ? Promise.resolve(q.shift()) : new Promise((r) => w.push(r))) }) } },
    event: (e) => push({ value: new TextEncoder().encode(`data: ${JSON.stringify(e)}\n\n`), done: false }), end: () => push({ done: true }) };
}
const pcm = () => ({ ok: true, body: { getReader: () => { let sent = false;
  return { read: async () => (sent ? { done: true } : (sent = true, { value: new Uint8Array(4800), done: false })) }; } } });

function harness() {
  const replies = [], speaks = [], log = jest.fn();
  const fetchImpl = jest.fn((url, opts) => {
    if (url.endsWith("/respond")) { const s = stream(); replies.push(s); return Promise.resolve(s.res); }
    if (url.endsWith("/speak")) { speaks.push(JSON.parse(opts.body).text); return Promise.resolve(pcm()); }
    return Promise.resolve({ ok: true, json: async () => ({ text: "" }) });
  });
  let playing = false;
  const player = { get playing() { return playing; }, output: "echo_cancelled", now: () => 0, ahead: () => 0,
    prepare: async () => null, play: jest.fn(() => { playing = true; return { start: 0, end: 1, gap: 0 }; }),
    stop: jest.fn(() => { const w = playing; playing = false; return w; }), hold: jest.fn(), close: jest.fn() };
  const { dc } = createCascadeConnection({ session: { token: "t", session: { model: "m" } }, caos: { turn_detection: {} },
    stream: {}, api: "/api", WebSocketImpl: FakeWs, fetchImpl, player, log, AudioCtx: Ctx });
  const ws = FakeWs.last;
  return { dc, ws, replies, speaks, log, player, end: () => { playing = false; player.onIdle?.(); },
    receipts: (n) => log.mock.calls.filter(([k]) => k === n).map(([, d]) => d.meta) };
}

test("a complete final sentence with no trailing space is spoken only at end of stream (backend done is not used)", async () => {
  const t = harness();
  t.ws.serve({ type: "ready" });
  t.dc.send(JSON.stringify({ type: "response.create" }));
  await flush();
  t.replies[0].event({ type: "text", delta: "Sure thing." });   // the whole reply, ending without whitespace
  t.replies[0].event({ type: "done", finish_reason: "stop" });
  await flush();
  expect(t.speaks).toEqual([]);                                 // still waiting: the receipt write precedes EOF
  t.replies[0].end();
  await flush();
  expect(t.speaks).toEqual(["Sure thing."]);
});

test("each reply's playback receipt carries its stage times, in order, numbers only", async () => {
  const t = harness();
  t.ws.serve({ type: "ready" });
  t.dc.send(JSON.stringify({ type: "response.create" }));
  await flush();
  const r = t.replies[0];
  r.event({ type: "text", delta: "Here you go. " }); await flush();
  r.event({ type: "text", delta: "All done." }); r.event({ type: "done", finish_reason: "stop" }); r.end();
  await flush(10);
  t.end(); await flush();
  const [m] = t.receipts("cascade_playback");
  const tm = m.timing;
  expect(Object.keys(tm).sort()).toEqual(["done_event_ms", "first_pcm_ms", "first_sentence_ms", "first_text_ms", "stream_end_ms"]);
  Object.values(tm).forEach((v) => expect(typeof v).toBe("number"));
  expect(tm.first_text_ms).toBeLessThanOrEqual(tm.first_sentence_ms);
  expect(tm.first_sentence_ms).toBeLessThanOrEqual(tm.first_pcm_ms);
  expect(tm.done_event_ms).toBeLessThanOrEqual(tm.stream_end_ms);
});

test("startup milestones are receipted once, at the first audible reply, with nulls for what was not observed", async () => {
  const t = harness();
  t.ws.onopen();
  t.ws.serve({ type: "ready" });
  await flush();
  procs[procs.length - 1].onaudioprocess({ inputBuffer: { getChannelData: () => new Float32Array(2048) } });
  t.dc.send(JSON.stringify({ type: "response.create" }));
  await flush();
  t.replies[0].event({ type: "text", delta: "Hey, Michael. " }); t.replies[0].end();
  await flush(10);
  const boots = t.receipts("cascade_startup");
  expect(boots).toHaveLength(1);
  const b = boots[0];
  expect(b).toMatchObject({ transport: "cascade", mic_state: "running", output: "echo_cancelled" });
  ["ws_open_ms", "service_ready_ms", "first_frame_ms", "output_ready_ms", "first_audio_ms"].forEach((k) => expect(typeof b[k]).toBe("number"));
  expect(b.service_ready_ms).toBeLessThanOrEqual(b.first_frame_ms);
  t.dc.send(JSON.stringify({ type: "response.create" }));
  await flush();
  t.replies[1].event({ type: "text", delta: "Again. " }); t.replies[1].end();
  await flush(10);
  expect(t.receipts("cascade_startup")).toHaveLength(1);
});

test("without a ready voice service the startup receipt still comes, after 10 s, saying what was not seen", () => {
  jest.useFakeTimers();
  const t = harness();
  jest.advanceTimersByTime(10000);
  expect(t.receipts("cascade_startup")).toEqual([expect.objectContaining({ service_ready_ms: null, first_frame_ms: null, first_audio_ms: null })]);
  jest.useRealTimers();
});
