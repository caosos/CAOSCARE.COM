import { DUCK_STEPS, duckRoomAudio, noteResidentVolumeChoice, resetResidentVolumeChoices, restoreRoomAudio, shouldDuckRoomAudio } from "../callAudioDuck";

const send = () => { const calls = []; const f = async (...a) => { calls.push(a); }; f.calls = calls; return f; };

beforeEach(() => resetResidentVolumeChoices());

test("TV volume duck is on by default and only an explicit room opt-out disables it", () => {
  expect(shouldDuckRoomAudio(undefined)).toBe(true);
  expect(shouldDuckRoomAudio({})).toBe(true);
  expect(shouldDuckRoomAudio({ tv_audio_duck: true })).toBe(true);
  expect(shouldDuckRoomAudio({ tv_audio_duck: false })).toBe(false);
});

test("an infrared TV is stepped down and back up by the same amount - never powered off", async () => {
  const s = send();
  const tv = { device_id: "tv1", kind: "tv", capabilities: ["power", "volume", "volume_step"], state: { power: "off" } };
  const r = await duckRoomAudio([tv], "214", s);
  await restoreRoomAudio(r, "214", s);
  expect(s.calls).toEqual([["214", "volume_step", -DUCK_STEPS, "tv", "tv1"], ["214", "volume_step", DUCK_STEPS, "tv", "tv1"]]);
  expect(s.calls.some((c) => c[1] === "power")).toBe(false);
});

test("a TV with a known volume goes down and back to its exact prior level; off or unknown is left alone", async () => {
  const s = send();
  const devs = [
    { device_id: "a", kind: "tv", protocol: "home_assistant", endpoint: "media_player.a", capabilities: ["power", "volume"], state: { power: "on", volume: 40 } },
    { device_id: "b", kind: "tv", capabilities: ["power", "volume"], state: { power: "off", volume: 40 } },
    { device_id: "c", kind: "light", capabilities: ["power"], state: { power: "on" } },
  ];
  await restoreRoomAudio(await duckRoomAudio(devs, "R", s), "R", s);
  expect(s.calls).toEqual([["R", "volume", 25, "tv", "a"], ["R", "volume", 40, "tv", "a"]]);
});

test("a resident's state-reported volume choice becomes the restore target", async () => {
  const s = send();
  const restore = await duckRoomAudio([{ device_id: "smart", kind: "tv", protocol: "home_assistant", endpoint: "media_player.smart", capabilities: ["volume"], state: { power: "on", volume: 20 } }], "214", s);
  noteResidentVolumeChoice("smart", 15);
  await restoreRoomAudio(restore, "214", s);
  expect(s.calls.map((c) => c[2])).toEqual([5, 15]);
});

test("a device that errors does not stop the others", async () => {
  const calls = [];
  const s = async (...a) => { calls.push(a); if (a[4] === "bad") throw new Error("x"); };
  const r = await duckRoomAudio([{ device_id: "bad", kind: "tv", capabilities: ["volume_step"] },
    { device_id: "ok", kind: "tv", capabilities: ["volume_step"] }], "R", s);
  expect(r.map((x) => x.device_id)).toEqual(["ok"]);
});
