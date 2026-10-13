import { createCallAudioCoordinator, DUCK_STEPS, duckRoomAudio, restoreRoomAudio } from "../callAudioDuck";

const send = () => { const calls = []; const f = async (...a) => { calls.push(a); }; f.calls = calls; return f; };

test("a TV with mute is muted at call start and the toggle pressed again at call end", async () => {
  const s = send();
  const tv = { device_id: "tv1", kind: "tv", capabilities: ["power", "volume", "volume_step", "mute"], state: {} };
  await restoreRoomAudio(await duckRoomAudio([tv], "214", s), "214", s);
  expect(s.calls).toEqual([["214", "mute", true, "tv", "tv1"], ["214", "mute", true, "tv", "tv1"]]);
});

test("an infrared TV without mute is stepped down and back up by the same amount - never powered off", async () => {
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
    { device_id: "a", kind: "tv", capabilities: ["power", "volume"], state: { power: "on", volume: 40 } },
    { device_id: "b", kind: "tv", capabilities: ["power", "volume"], state: { power: "off", volume: 40 } },
    { device_id: "c", kind: "light", capabilities: ["power"], state: { power: "on" } },
  ];
  await restoreRoomAudio(await duckRoomAudio(devs, "R", s), "R", s);
  expect(s.calls).toEqual([["R", "volume", 25, "tv", "a"], ["R", "volume", 40, "tv", "a"]]);
});

test("a device that errors does not stop the others", async () => {
  const calls = [];
  const s = async (...a) => { calls.push(a); if (a[4] === "bad") throw new Error("x"); };
  const r = await duckRoomAudio([{ device_id: "bad", kind: "tv", capabilities: ["volume_step"] },
    { device_id: "ok", kind: "tv", capabilities: ["volume_step"] }], "R", s);
  expect(r.map((x) => x.device_id)).toEqual(["ok"]);
});

test("rapid close then wake is serialized as duck, restore, duck with no power action", async () => {
  const calls = [];
  let releaseFirst;
  const firstCanFinish = new Promise((resolve) => { releaseFirst = resolve; });
  const sendBlockedOnce = jest.fn(async (...args) => {
    calls.push(args);
    if (calls.length === 1) await firstCanFinish;
  });
  const audio = createCallAudioCoordinator(sendBlockedOnce);
  const tv = { device_id: "tv1", kind: "tv", capabilities: ["power", "volume_step"], state: { power: "on" } };

  const firstWake = audio.begin([tv], "214");
  await Promise.resolve(); // first duck has entered send() and is still in flight
  const close = audio.end();
  const rapidWake = audio.begin([tv], "214");
  expect(calls).toEqual([["214", "volume_step", -DUCK_STEPS, "tv", "tv1"]]);

  releaseFirst();
  await Promise.all([firstWake, close, rapidWake]);
  expect(calls).toEqual([
    ["214", "volume_step", -DUCK_STEPS, "tv", "tv1"],
    ["214", "volume_step", DUCK_STEPS, "tv", "tv1"],
    ["214", "volume_step", -DUCK_STEPS, "tv", "tv1"],
  ]);
  expect(calls.some((call) => call[1] === "power")).toBe(false);
});

test("rapid close then wake preserves mute-first toggle ordering", async () => {
  const s = send();
  const audio = createCallAudioCoordinator(s);
  const tv = { device_id: "tv1", kind: "tv", capabilities: ["power", "volume_step", "mute"], state: {} };
  await audio.begin([tv], "214");
  const close = audio.end();
  const wake = audio.begin([tv], "214");
  await Promise.all([close, wake]);
  expect(s.calls).toEqual([
    ["214", "mute", true, "tv", "tv1"],
    ["214", "mute", true, "tv", "tv1"],
    ["214", "mute", true, "tv", "tv1"],
  ]);
  expect(s.calls.some((call) => call[1] === "power")).toBe(false);
});
