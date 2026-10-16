// get_room_status speaks from the server inventory; blinds only claim a move the device confirmed;
// check_medication_status relays the backend's truthful line (aria-room-runtime-fixes-001).
import { executeDeviceTool } from "../realtimeDeviceTools";
import { executeCareTool } from "../realtimeCareControl";
import { roomStatusResult } from "../realtimeRoomStatus";

const INV = {
  ok: true, room: "214", not_connected: ["motorized blinds"],
  connected: [
    { name: "TV", kind: "tv", protocol: "ir_blaster", capabilities: ["power", "volume_step", "mute"],
      actions: ["turn it on or off", "turn the volume up or down", "mute or unmute it"], state_feedback: "one_way", reported_state: {} },
    { name: "overhead light", kind: "light", protocol: "home_assistant", capabilities: ["power", "brightness"],
      actions: ["turn it on or off", "change its brightness"], state_feedback: "reported", reported_state: { power: "on", brightness: 50 } },
  ],
  summary: "Connected in this room: the TV: I can turn it on or off ... Not connected in this room: motorized blinds.",
};

afterEach(() => { delete global.fetch; });

test("get_room_status asks the inventory route and speaks readings only from reporting devices", async () => {
  global.fetch = jest.fn(async () => ({ ok: true, json: async () => INV }));
  const r = await executeDeviceTool({ name: "get_room_status", args: {}, ctx: { room: "214" } });
  expect(global.fetch.mock.calls[0][0]).toMatch(/\/devices\/public\/room\/214\/inventory$/);
  expect(r.ok).toBe(true);
  expect(r.message).toMatch(/^Current readings: the overhead light is on, brightness 50\. Connected in this room/);
  expect(r.message).toContain("Not connected in this room: motorized blinds.");
  expect(r.message).not.toMatch(/the TV is (on|off)/);          // one-way IR: no invented state
  expect(r.not_connected).toEqual(["motorized blinds"]);
});

test("an empty room inventory is still an answer", () => {
  const r = roomStatusResult({ connected: [], not_connected: ["lights", "TV"], summary: "No controllable devices are connected in this room." });
  expect(r.message).toBe("No controllable devices are connected in this room.");
});

const blindsCtx = { room: "9", last_user_text: "open the blinds please" };
test("blinds on a device that reports back are confirmed; a one-way device is only 'sent'", async () => {
  const dev = { device_id: "b", label: "Room 9 blinds", kind: "blinds", capabilities: ["position"], online: true };
  global.fetch = jest.fn(async (url) => {
    if (String(url).includes("/by-room/")) return { ok: true, json: async () => [dev] };
    return { ok: true, json: async () => ({ verified: true, state: { position: 100 } }) };
  });
  const ok = await executeDeviceTool({ name: "set_blinds", args: { action: "open" }, ctx: blindsCtx });
  expect(ok.message).toBe("the blinds are now fully open.");
  global.fetch = jest.fn(async (url) => {
    if (String(url).includes("/by-room/")) return { ok: true, json: async () => [dev] };
    return { ok: true, json: async () => ({ status: "queued", verified: false, state: { position: 100 } }) };
  });
  const sent = await executeDeviceTool({ name: "set_blinds", args: { action: "open" }, ctx: blindsCtx });
  expect(sent.verified).toBe(false);
  expect(sent.message).toMatch(/^I sent the blinds the command to be fully open, but they can't report back/);
  global.fetch = jest.fn(async (url) => (String(url).includes("/by-room/") ? { ok: true, json: async () => [] } : { ok: false }));
  const none = await executeDeviceTool({ name: "set_blinds", args: { action: "open" }, ctx: blindsCtx });
  expect(none).toEqual({ ok: false, message: "there's no blinds set up in this room." });
});

test("check_medication_status relays the backend line and never improvises", async () => {
  global.fetch = jest.fn(async () => ({ ok: true, json: async () => ({
    spoken: "I don't have confirmation that anyone is on the way yet. I'm sending a high-priority request to nursing now.",
    staff_confirmed: false, task_id: "task_1", receipt_id: "rcpt_1", scheduled_today: [] }) }));
  const r = await executeCareTool({ name: "check_medication_status", args: { resident_words: "is someone coming?" },
    ctx: { room: "214", resident_id: "res_1", session_id: "rt_1" } });
  const body = JSON.parse(global.fetch.mock.calls[0][1].body);
  expect(global.fetch.mock.calls[0][0]).toMatch(/\/medications\/public\/status-check$/);
  expect(body).toMatchObject({ resident_id: "res_1", room: "214", conversation_session_id: "rt_1", resident_words: "is someone coming?" });
  expect(r).toMatchObject({ ok: true, staff_confirmed: false, task_id: "task_1", receipt_id: "rcpt_1" });
  global.fetch = jest.fn(async () => ({ ok: false, status: 500 }));
  const fail = await executeCareTool({ name: "check_medication_status", args: {}, ctx: { room: "214" } });
  expect(fail.ok).toBe(false);
  expect(fail.message).toMatch(/nothing was sent/);
});
