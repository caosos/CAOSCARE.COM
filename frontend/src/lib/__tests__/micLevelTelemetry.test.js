import { createLevelSegmenter, startMicLevelTelemetry } from "../micLevelTelemetry";

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
