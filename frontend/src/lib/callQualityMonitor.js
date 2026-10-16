// Bounded WebRTC call-quality diagnostics (aria-room-runtime-fixes-001, 2026-10-16: Room 214 audio
// "sounded like a poor cellular connection"). Samples RTCPeerConnection.getStats() every SAMPLE_MS,
// sums each REPORT_MS window into a handful of numbers, and posts one window per REPORT_MS plus a
// final window at teardown to /realtime-diagnostics/call-quality, which grades it GOOD / DEGRADED / BAD
// (thresholds live in backend/routes/realtime_call_quality.py). Never audio, never per-packet logs.
// Also measured: how late the page's own timer fires (a stalled local page, not the network) and the
// provider's response latency (resident stops speaking -> Aria's audio starts).
import { API } from "./api";

export const SAMPLE_MS = 5000;
export const REPORT_MS = 30000;

const n = (v) => (typeof v === "number" && Number.isFinite(v) ? v : 0);
const round = (v, d = 1) => Math.round(v * 10 ** d) / 10 ** d;

/** Pull the cumulative counters we use out of one getStats() report (Map-like or array of stats). */
export function readStats(report) {
  const all = [];
  report?.forEach?.((s) => all.push(s));
  const byId = Object.fromEntries(all.map((s) => [s.id, s]));
  const inbound = all.find((s) => s.type === "inbound-rtp" && (s.kind || s.mediaType) === "audio") || {};
  const remote = all.find((s) => s.type === "remote-inbound-rtp" && (s.kind || s.mediaType) === "audio") || {};
  const pair = all.find((s) => s.type === "candidate-pair" && s.state === "succeeded" && (s.nominated || s.selected))
    || all.find((s) => s.type === "candidate-pair" && s.state === "succeeded") || {};
  const local = byId[pair.localCandidateId] || {};
  return {
    packetsReceived: n(inbound.packetsReceived), packetsLost: n(inbound.packetsLost),
    jitterMs: n(inbound.jitter) * 1000, concealedSamples: n(inbound.concealedSamples),
    totalSamplesReceived: n(inbound.totalSamplesReceived), concealmentEvents: n(inbound.concealmentEvents),
    remoteFractionLost: n(remote.fractionLost), rttMs: n(pair.currentRoundTripTime || remote.roundTripTime) * 1000,
    candidateType: local.candidateType || null, networkType: local.networkType || null,
  };
}

/** One window's metrics from the counters at its start and end plus its maxima (pure). */
export function windowMetrics(start, end, extra = {}) {
  const received = Math.max(0, end.packetsReceived - start.packetsReceived);
  const lost = Math.max(0, end.packetsLost - start.packetsLost);
  const samples = Math.max(0, end.totalSamplesReceived - start.totalSamplesReceived);
  const concealed = Math.max(0, end.concealedSamples - start.concealedSamples);
  const lat = [...(extra.latencies || [])].sort((a, b) => a - b);
  return {
    packets_received: received, packets_lost: lost,
    loss_pct: received + lost ? round((100 * lost) / (received + lost)) : 0,
    remote_loss_pct: round(100 * (extra.maxRemoteFractionLost ?? end.remoteFractionLost)),
    jitter_ms: round(extra.maxJitterMs ?? end.jitterMs), rtt_ms: round(extra.maxRttMs ?? end.rttMs),
    concealed_pct: samples ? round((100 * concealed) / samples) : 0,
    concealment_events: Math.max(0, end.concealmentEvents - start.concealmentEvents),
    ui_lag_ms_max: round(extra.uiLagMsMax || 0, 0),
    ...(lat.length ? { response_latency_ms_median: lat[Math.floor(lat.length / 2)], response_samples: lat.length } : {}),
    connection_state: extra.connectionState || null, ice_state: extra.iceState || null,
    candidate_type: end.candidateType, network_type: end.networkType,
  };
}

function defaultPost(body) {
  try {
    fetch(`${API}/realtime-diagnostics/call-quality`, {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body), keepalive: true,
    }).catch(() => {});
  } catch { /* diagnostics never touch the call */ }
}

export function startCallQualityMonitor({ pc, dc, sessionId, room, post = defaultPost, now = () => Date.now(),
  setTimer = setInterval, clearTimer = clearInterval }) {
  let start = null, last = null, windowStartAt = now(), lastTick = now(), stopped = false;
  let maxJitterMs = 0, maxRttMs = 0, maxRemoteFractionLost = 0, uiLagMsMax = 0, latencies = [], speechStoppedAt = null;
  const reset = () => { start = last; windowStartAt = now(); maxJitterMs = maxRttMs = maxRemoteFractionLost = uiLagMsMax = 0; latencies = []; };
  const send = (phase, reason) => {
    if (!start || !last) return;
    post({ session_id: sessionId, room, phase, reason: reason || null, window_ms: now() - windowStartAt,
      metrics: windowMetrics(start, last, { maxJitterMs, maxRttMs, maxRemoteFractionLost, uiLagMsMax, latencies,
        connectionState: pc?.connectionState, iceState: pc?.iceConnectionState }) });
  };
  const sample = async () => {
    const t = now();
    uiLagMsMax = Math.max(uiLagMsMax, t - lastTick - SAMPLE_MS);   // timer fired late: the page itself stalled
    lastTick = t;
    let s;
    try { s = readStats(await pc.getStats()); } catch { return; }
    if (stopped) return;
    if (!start) { start = s; windowStartAt = t; }
    last = s;
    maxJitterMs = Math.max(maxJitterMs, s.jitterMs); maxRttMs = Math.max(maxRttMs, s.rttMs);
    maxRemoteFractionLost = Math.max(maxRemoteFractionLost, s.remoteFractionLost);
    if (t - windowStartAt >= REPORT_MS) { send("interval"); reset(); }
  };
  const onMessage = (ev) => {
    let type;
    try { type = JSON.parse(ev.data)?.type; } catch { return; }
    if (type === "input_audio_buffer.speech_stopped") speechStoppedAt = now();
    else if (type === "output_audio_buffer.started" && speechStoppedAt !== null) {
      latencies.push(now() - speechStoppedAt); speechStoppedAt = null;
    }
  };
  dc?.addEventListener?.("message", onMessage);
  const timer = setTimer(sample, SAMPLE_MS);
  sample();
  return {
    sample,
    /** Teardown: one final window from what was already sampled (the peer is closing). */
    stop(reason = "session_end") {
      if (stopped) return;
      stopped = true;
      clearTimer(timer);
      try { dc?.removeEventListener?.("message", onMessage); } catch { /* closing */ }
      send("final", reason);
    },
  };
}
