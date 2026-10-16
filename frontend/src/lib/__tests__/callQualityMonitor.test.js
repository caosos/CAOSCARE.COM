// Call-quality windows (aria-room-runtime-fixes-001): bounded posts (one per 30 s window + one final),
// loss/jitter/RTT/concealment from real getStats() shapes, local page stalls and provider latency.
import { readStats, windowMetrics, startCallQualityMonitor, SAMPLE_MS, REPORT_MS } from "../callQualityMonitor";

const report = ({ rx, lost, jitter, concealed, samples, rtt, fl = 0 }) => new Map([
  ["in", { id: "in", type: "inbound-rtp", kind: "audio", packetsReceived: rx, packetsLost: lost, jitter,
    concealedSamples: concealed, totalSamplesReceived: samples, concealmentEvents: Math.floor(concealed / 100) }],
  ["rin", { id: "rin", type: "remote-inbound-rtp", kind: "audio", fractionLost: fl, roundTripTime: rtt }],
  ["cp", { id: "cp", type: "candidate-pair", state: "succeeded", nominated: true, currentRoundTripTime: rtt, localCandidateId: "lc" }],
  ["lc", { id: "lc", type: "local-candidate", candidateType: "srflx", networkType: "wifi" }],
]);

test("readStats pulls audio counters, RTT and the local candidate", () => {
  const s = readStats(report({ rx: 1000, lost: 10, jitter: 0.012, concealed: 480, samples: 48000, rtt: 0.08 }));
  expect(s).toMatchObject({ packetsReceived: 1000, packetsLost: 10, jitterMs: 12, rttMs: 80, candidateType: "srflx", networkType: "wifi" });
});

test("a degraded window: 6% loss, 45 ms jitter, 7% concealment", () => {
  const a = readStats(report({ rx: 1000, lost: 0, jitter: 0.01, concealed: 0, samples: 0, rtt: 0.05 }));
  const b = readStats(report({ rx: 2410, lost: 90, jitter: 0.045, concealed: 6720, samples: 96000, rtt: 0.12 }));
  const m = windowMetrics(a, b, { maxJitterMs: 45, maxRttMs: 120, latencies: [900, 1200, 4000] });
  expect(m).toMatchObject({ packets_received: 1410, packets_lost: 90, loss_pct: 6, jitter_ms: 45, rtt_ms: 120,
    concealed_pct: 7, response_latency_ms_median: 1200, candidate_type: "srflx" });
});

test("posts one window per REPORT_MS and one final window; measures UI stalls and response latency", async () => {
  let t = 0;
  let rx = 0;
  const posts = [];
  const pc = { connectionState: "connected", iceConnectionState: "connected",
    getStats: async () => report({ rx: (rx += 250), lost: 0, jitter: 0.004, concealed: 0, samples: rx * 960, rtt: 0.04 }) };
  const listeners = [];
  const dc = { addEventListener: (_, f) => listeners.push(f), removeEventListener: () => {} };
  const m = startCallQualityMonitor({ pc, dc, sessionId: "rt_x", room: "214", post: (b) => posts.push(b),
    now: () => t, setTimer: () => 1, clearTimer: () => {} });
  await Promise.resolve();
  listeners[0]({ data: JSON.stringify({ type: "input_audio_buffer.speech_stopped" }) });
  t += 700;
  listeners[0]({ data: JSON.stringify({ type: "output_audio_buffer.started" }) });
  for (let i = 0; i < REPORT_MS / SAMPLE_MS; i += 1) { t += SAMPLE_MS + (i === 2 ? 1800 : 0); await m.sample(); }
  expect(posts).toHaveLength(1);
  expect(posts[0]).toMatchObject({ session_id: "rt_x", phase: "interval", room: "214" });
  expect(posts[0].metrics).toMatchObject({ loss_pct: 0, response_latency_ms_median: 700, connection_state: "connected" });
  expect(posts[0].metrics.ui_lag_ms_max).toBeGreaterThanOrEqual(1800);
  t += SAMPLE_MS; await m.sample();
  m.stop("end_call_tool");
  m.stop("component_unmount");
  expect(posts).toHaveLength(2);
  expect(posts[1]).toMatchObject({ phase: "final", reason: "end_call_tool" });
});
