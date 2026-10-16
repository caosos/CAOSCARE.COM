// Call-audio duck/restore as a state machine (aria-room-runtime-fixes-001, Room 214 TV left muted
// 2026-10-16): every end path restores exactly once, a reload/unmount between duck and restore is undone
// on the next mount, restore is idempotent, and nothing ever sends a power command.
import { createCallAudioCoordinator, LEDGER_KEY } from "../callAudioDuck";

const TV = { device_id: "dev_tv", kind: "tv", capabilities: ["power", "volume", "volume_step", "mute"], state: { power: "on" } };
const SPK = { device_id: "dev_spk", kind: "speaker", capabilities: ["volume_step"], state: {} };

function memoryStorage() {
  const m = new Map();
  return { getItem: (k) => (m.has(k) ? m.get(k) : null), setItem: (k, v) => m.set(k, String(v)), removeItem: (k) => m.delete(k), m };
}
function harness({ failTimes = 0 } = {}) {
  const sent = [];
  const logs = [];
  let failures = failTimes;
  const send = jest.fn(async (room, action, value, kind, id) => {
    if (failures > 0 && sent.length > 0) { failures -= 1; throw new Error("network"); }
    sent.push(`${id}:${action}:${value}`);
  });
  const storage = memoryStorage();
  const make = () => createCallAudioCoordinator(send, { storage, log: (e, d) => logs.push([e, d.reason || null]) });
  return { sent, logs, storage, send, make };
}

test.each(["end_call_tool", "cancel_call", "webrtc_connection_failed", "setup_failed", "kiosk_unmount", "alert_resolved"])(
  "end path %s: muted exactly once, restored exactly once, ledger empty", async (reason) => {
    const h = harness();
    const c = h.make();
    await c.begin([TV], "214");
    expect(JSON.parse(h.storage.getItem(LEDGER_KEY)).restore).toHaveLength(1);
    await c.end(reason);
    expect(h.sent).toEqual(["dev_tv:mute:true", "dev_tv:mute:true"]);
    expect(h.storage.getItem(LEDGER_KEY)).toBeNull();
    expect(h.logs).toEqual([["call_audio_ducked", null], ["call_audio_restored", reason]]);
  });

test("duplicate close (end_call then alert-resolution cancel) restores once", async () => {
  const h = harness();
  const c = h.make();
  await c.begin([TV], "214");
  await Promise.all([c.end("end_call_tool"), c.end("cancel_call")]);
  await c.end("kiosk_unmount");
  expect(h.sent).toEqual(["dev_tv:mute:true", "dev_tv:mute:true"]);
});

test("page reload between duck and restore: the next mount restores once, a second recover does nothing", async () => {
  const h = harness();
  await h.make().begin([TV, SPK], "214");          // page dies here, no end()
  const fresh = h.make();                          // reload: new coordinator, same storage
  await fresh.recover();
  await fresh.recover();
  await fresh.end("kiosk_unmount");
  expect(h.sent).toEqual(["dev_tv:mute:true", "dev_spk:volume_step:-15", "dev_tv:mute:true", "dev_spk:volume_step:15"]);
  expect(h.logs.map((l) => l[0])).toEqual(["call_audio_ducked", "call_audio_recovered", "call_audio_restored"]);
  expect(h.storage.getItem(LEDGER_KEY)).toBeNull();
});

test("reload in the middle of the duck: only the press that was sent is undone", async () => {
  const h = harness();
  let hang;
  const send = async (room, action, value, kind, id) => {
    if (id === "dev_spk" && !hang) return new Promise((r) => { hang = r; });   // never completes on the first page
    h.sent.push(`${id}:${action}:${value}`);
  };
  createCallAudioCoordinator(send, { storage: h.storage }).begin([TV, SPK], "214");
  await new Promise((r) => setTimeout(r, 0));
  const fresh = createCallAudioCoordinator(send, { storage: h.storage });
  await fresh.recover();
  expect(h.sent).toEqual(["dev_tv:mute:true", "dev_tv:mute:true"]);
});

test("activation replaced mid-call: the old duck is undone before the new one; the TV ends where it started", async () => {
  const h = harness();
  const c = h.make();
  await c.begin([TV], "214");
  await c.begin([TV], "214");
  await c.end("end_call_tool");
  expect(h.sent).toHaveLength(4);                  // duck, undo, duck, undo: an even number of mute toggles
  expect(h.logs.map((l) => l[1])).toContain("replaced_by_new_call");
});

test("rapid wake, end, wake, end stays paired and serialized", async () => {
  const h = harness();
  const c = h.make();
  c.begin([TV], "214"); c.end("end_call_tool"); c.begin([TV], "214");
  await c.end("end_call_tool");
  expect(h.sent).toEqual(Array(4).fill("dev_tv:mute:true"));
  expect(h.storage.getItem(LEDGER_KEY)).toBeNull();
});

test("a failed restore press is retried once; a second failure is logged, never resent later", async () => {
  const ok = harness({ failTimes: 1 });
  const c = ok.make();
  await c.begin([TV], "214");
  await c.end("end_call_tool");
  expect(ok.sent).toEqual(["dev_tv:mute:true", "dev_tv:mute:true"]);
  expect(ok.logs.pop()[0]).toBe("call_audio_restored");

  const bad = harness({ failTimes: 2 });
  const d = bad.make();
  await d.begin([TV], "214");
  await d.end("end_call_tool");
  expect(bad.logs.pop()[0]).toBe("call_audio_restore_failed");
  await bad.make().recover();                      // nothing left to replay: no double toggle later
  expect(bad.sent).toEqual(["dev_tv:mute:true"]);
});

test("no call path ever sends a power command", async () => {
  const h = harness();
  const c = h.make();
  await c.begin([TV, SPK], "214");
  await c.begin([TV], "214");
  await c.end("webrtc_connection_failed");
  await h.make().recover();
  expect(h.send.mock.calls.every(([, action]) => action !== "power")).toBe(true);
});
