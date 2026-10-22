import { createLevelSegmenter, createMicVoice, micDiagnosticsAllowed, startMicLevelTelemetry } from "../micLevelTelemetry";

const run = (frames) => {
  const seg = createLevelSegmenter(0);
  return frames.map((f) => seg(f)).filter(Boolean);
};
const quiet = (n) => Array(n).fill(0.0001);
const speech = (n, v = 0.05) => Array(n).fill(v);

test("one summary per speech segment, numbers only", () => {
  const out = run([...quiet(20), ...speech(17), ...quiet(8), ...speech(25), ...quiet(8)]);
  expect(out).toHaveLength(2);
  expect(Object.keys(out[0]).sort()).toEqual(
    ["duration_s", "mean_dbfs", "noise_floor_dbfs", "peak_dbfs", "speech_frames", "start_ms"]);
  expect(out[0].speech_frames).toBe(17);
  expect(out[0].peak_dbfs).toBeGreaterThan(-30);
});

test("a pause shorter than 0.5 s stays one segment; steady fan-level noise never opens one", () => {
  expect(run([...quiet(20), ...speech(10), ...quiet(3), ...speech(10), ...quiet(8)])).toHaveLength(1);
  expect(run(Array(300).fill(0.002))).toHaveLength(0);
});

test("a click shorter than 0.2 s is ignored", () => {
  expect(run([...quiet(20), ...speech(1), ...quiet(8)])).toHaveLength(0);
});

test("telemetry is off by default and does not touch the stream", () => {
  const stream = { getAudioTracks: () => { throw new Error("must not be touched"); } };
  expect(typeof startMicLevelTelemetry(stream, () => {})).toBe("function");
});

test("measured only where the build names the kiosk: flag alone, list alone or another kiosk is off", () => {
  const room214 = "kio_dc8c06a19608";
  const on = { REACT_APP_MIC_LEVEL_TELEMETRY: "1", REACT_APP_MIC_LEVEL_TELEMETRY_KIOSKS: ` ${room214} ,kio_other_test` };
  expect(micDiagnosticsAllowed(room214, on)).toBe(true);
  expect(micDiagnosticsAllowed("kio_another_resident", on)).toBe(false);
  expect(micDiagnosticsAllowed(undefined, on)).toBe(false);
  expect(micDiagnosticsAllowed("", { ...on, REACT_APP_MIC_LEVEL_TELEMETRY_KIOSKS: "" })).toBe(false);
  expect(micDiagnosticsAllowed(room214, { REACT_APP_MIC_LEVEL_TELEMETRY: "1" })).toBe(false);       // no list: no one
  expect(micDiagnosticsAllowed(room214, { REACT_APP_MIC_LEVEL_TELEMETRY_KIOSKS: room214 })).toBe(false); // no flag
  expect(micDiagnosticsAllowed(room214)).toBe(false);                                                // this test build
});

test("when allowed it logs processed-track numbers only; a broken audio API never throws", () => {
  jest.useFakeTimers();
  const frames = [...Array(20).fill(0.0001), ...Array(17).fill(0.05), ...Array(8).fill(0.0001)];
  let i = 0;
  const analyser = { fftSize: 0, getFloatTimeDomainData: (b) => b.fill(frames[Math.min(i++, frames.length - 1)]) };
  window.AudioContext = function () {
    return { createAnalyser: () => analyser, createMediaStreamSource: () => ({ connect() {} }), close() {} };
  };
  const stream = { getAudioTracks: () => [{ readyState: "live" }] };
  const log = jest.fn();
  const stop = startMicLevelTelemetry(stream, log, { allowed: true });
  jest.advanceTimersByTime(frames.length * 100);
  stop();
  expect(log).toHaveBeenCalledTimes(1);
  const [type, { meta }] = log.mock.calls[0];
  expect(type).toBe("mic_level");
  expect(meta.source).toBe("processed_track");
  expect(Object.values(meta).every((v) => typeof v === "number" || v === "processed_track")).toBe(true);

  window.AudioContext = function () { throw new Error("no audio"); };
  expect(typeof startMicLevelTelemetry(stream, log, { allowed: true })).toBe("function");
  jest.useRealTimers();
  delete window.AudioContext;
});

// Room 214 rt_4ze7jvrt (2026-10-22 02:33 CDT), ms relative to the transcript: voice from -1,880 through +420,
// server speech_stopped at -540. The meter's open segment says he was still talking when "go away" came back.
test("rt_4ze7jvrt: voice that runs through the server's speech_stopped is still talking", () => {
  let t = 100000;
  const seg = createLevelSegmenter(0);
  const voice = createMicVoice(() => t);
  voice.attach(seg.open);
  const feed = (frames) => frames.forEach((f) => { seg(f, f, t); t += 100; });
  feed(quiet(20));
  const voiceStart = t;
  feed(speech(14));                        // -1,880 .. -480
  const stoppedAt = voiceStart + 1340;     // server speech_stopped -540 (inside his voice)
  feed(speech(5));                         // .. +20: the transcript lands now
  expect(voice.stillTalking(stoppedAt)).toBe(true);
  feed(quiet(5));                          // 0.5 s of quiet closes the segment
  expect(voice.stillTalking(stoppedAt)).toBe(false);
});

test("a goodbye whose voice ended before the server's second of silence is not still talking", () => {
  let t = 100000;
  const seg = createLevelSegmenter(0);
  const voice = createMicVoice(() => t);
  voice.attach(seg.open);
  const feed = (frames) => frames.forEach((f) => { seg(f, f, t); t += 100; });
  feed([...quiet(20), ...speech(8)]);
  const lastVoice = t;
  feed(quiet(4));                          // still open (needs 5 quiet frames to close) but not voiced lately
  expect(voice.stillTalking(lastVoice + 1100)).toBe(false);
  feed(quiet(20));
  // rt_lcnze2u9 / rt_tacnqxsf: a faint sound that starts near speech_stopped is not talking through it
  const stoppedAt = t;
  feed(speech(3));
  expect(voice.stillTalking(stoppedAt)).toBe(false);
  expect(voice.stillTalking(null)).toBe(false);
  expect(createMicVoice().stillTalking(stoppedAt)).toBe(false);   // no meter attached (other rooms): never
});
