/**
 * SC-12: TV and thermostat commands carry the conversation session_id the
 * same way light commands do, so device_commands and receipts link back to
 * the conversation. A turn without a session sends null - never a made-up id.
 */
process.env.REACT_APP_BACKEND_URL = "http://127.0.0.1:8000";
import { executeDeviceTool } from "../realtimeDeviceTools";

const TV = { device_id: "dev_tv", kind: "tv", capabilities: ["power", "volume", "input"], inputs: ["TV", "HDMI 1"], state: { power: "off" } };
const THERMOSTAT = { device_id: "dev_thermo", kind: "thermostat", capabilities: ["power", "temperature"], state: { power: "on", temperature: 72 } };
const LIGHT = { device_id: "dev_light", kind: "light", capabilities: ["power"], state: { power: "off" } };

function ctx(overrides = {}) {
  return { resident_id: "res_test", room: "T1", session_id: "rt_sess_1", turn_suspect: false, ...overrides };
}

beforeEach(() => {
  global.fetch = jest.fn(async (url) => {
    if (String(url).includes("/devices/public/by-room/")) return { ok: true, json: async () => [TV, THERMOSTAT, LIGHT] };
    return { ok: true, json: async () => ({ ok: true }) };
  });
});

function commandBodies() {
  return global.fetch.mock.calls.filter(([u]) => String(u).includes("/command")).map(([, o]) => JSON.parse(o.body));
}

test("toggle_tv power and grounded volume both carry session_id", async () => {
  const r = await executeDeviceTool({ name: "toggle_tv", args: { state: "on", volume: 30 }, ctx: ctx({ last_user_text: "turn on the TV at volume 30" }) });
  expect(r.ok).toBe(true);
  const bodies = commandBodies();
  expect(bodies.map((b) => b.action)).toEqual(["power", "volume"]);
  bodies.forEach((b) => expect(b).toMatchObject({ session_id: "rt_sess_1", device_id: "dev_tv" }));
});

test("set_tv_input carries session_id", async () => {
  await executeDeviceTool({ name: "set_tv_input", args: { input: "HDMI 1" }, ctx: ctx() });
  expect(commandBodies()).toEqual([expect.objectContaining({ action: "input", session_id: "rt_sess_1" })]);
});

test("adjust_room_temperature carries session_id", async () => {
  await executeDeviceTool({ name: "adjust_room_temperature", args: { target_f: 70 }, ctx: ctx() });
  expect(commandBodies()).toEqual([expect.objectContaining({ action: "temperature", value: 70, session_id: "rt_sess_1" })]);
});

test("toggle_light keeps carrying session_id (existing behaviour)", async () => {
  await executeDeviceTool({ name: "toggle_light", args: { state: "on" }, ctx: ctx() });
  expect(commandBodies()).toEqual([expect.objectContaining({ action: "power", session_id: "rt_sess_1" })]);
});

test("no session: TV and thermostat send session_id null, not a fabricated id", async () => {
  await executeDeviceTool({ name: "toggle_tv", args: { state: "off" }, ctx: ctx({ session_id: undefined }) });
  await executeDeviceTool({ name: "adjust_room_temperature", args: { target_f: 68 }, ctx: ctx({ session_id: undefined }) });
  const bodies = commandBodies();
  expect(bodies).toHaveLength(2);
  bodies.forEach((b) => expect(b.session_id).toBeNull());
});
