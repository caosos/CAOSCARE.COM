// Event-only level telemetry for the PROCESSED microphone track - the audio
// the browser actually sends to OpenAI (after echo cancellation, noise
// suppression and auto-gain). Numbers only: no samples, no transcripts.
// Off unless REACT_APP_MIC_LEVEL_TELEMETRY=1 at build time. See
// docs/reports/2026-10-09-audio-turn-triage.md for why it exists: the wake
// listener sees the RAW eMeet signal, the server sees this one, and the
// difference between them is the unanswered question.
const FRAME_S = 0.1;
const ABOVE_FLOOR_DB = 10;
const MIN_DBFS = -50;
const QUIET_FRAMES_TO_CLOSE = 5;   // same 0.5 s rule as room-node/aria_wake/levels.py

const db = (x) => Math.round(20 * Math.log10(Math.max(x, 1e-6)) * 10) / 10;

// Pure: feed one RMS (linear, 0-1) per 100 ms frame; returns a summary when a
// speech segment closes. `t0` is the epoch ms of the first frame.
export function createLevelSegmenter(t0 = Date.now()) {
  let floor = null, n = 0, seg = null;
  return function frame(rms, peak = rms) {
    floor = floor === null || rms < floor ? rms : floor * 0.999 + rms * 0.001;
    const speech = db(rms) > Math.max(db(floor) + ABOVE_FLOOR_DB, MIN_DBFS);
    n += 1;
    let out = null;
    if (speech) {
      if (!seg) seg = { start: n - 1, speech: 0, quiet: 0, frames: 0, peak: 0, sq: 0 };
      seg.quiet = 0; seg.speech += 1;
    } else if (seg) seg.quiet += 1;
    if (seg) {
      seg.frames += 1; seg.peak = Math.max(seg.peak, peak); seg.sq += rms * rms;
      if (seg.quiet >= QUIET_FRAMES_TO_CLOSE) {
        if (seg.speech >= 2) {
          out = { start_ms: Math.round(t0 + seg.start * FRAME_S * 1000), duration_s: Math.round(seg.frames * FRAME_S * 10) / 10,
            speech_frames: seg.speech, peak_dbfs: db(seg.peak), mean_dbfs: db(Math.sqrt(seg.sq / seg.frames)),
            noise_floor_dbfs: db(floor) };
        }
        seg = null;
      }
    }
    return out;
  };
}

export function startMicLevelTelemetry(stream, log) {
  if (process.env.REACT_APP_MIC_LEVEL_TELEMETRY !== "1") return () => {};
  let ctx, timer;
  try {
    ctx = new (window.AudioContext || window.webkitAudioContext)();
    const analyser = ctx.createAnalyser();
    analyser.fftSize = 2048;
    ctx.createMediaStreamSource(stream).connect(analyser);   // never connected to the speakers
    const buf = new Float32Array(analyser.fftSize);
    const track = stream.getAudioTracks()[0];
    const seg = createLevelSegmenter();
    const stop = () => { clearInterval(timer); try { ctx.close(); } catch { /* already closed */ } };
    timer = setInterval(() => {
      if (!track || track.readyState === "ended") return stop();
      analyser.getFloatTimeDomainData(buf);
      let sq = 0, pk = 0;
      for (let i = 0; i < buf.length; i++) { sq += buf[i] * buf[i]; pk = Math.max(pk, Math.abs(buf[i])); }
      const summary = seg(Math.sqrt(sq / buf.length) + 1e-9, pk);
      if (summary) log("mic_level", { meta: { ...summary, source: "processed_track" } });
    }, FRAME_S * 1000);
    return stop;
  } catch { return () => {}; }   // diagnostic only - never affect the call
}
