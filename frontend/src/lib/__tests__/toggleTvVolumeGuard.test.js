/**
 * Regression test for the toggle_tv volume grounding guard
 * (docs/PROJECT_STATE.md, 2026-08-30 incident). Reproduces the exact live
 * failure: the transcript "Hello Lab" (garbled/nonsense) led the model to
 * call toggle_tv(state="on", volume=11) - neither the power nor the 11 was
 * grounded in anything the resident's saved transcript actually says.
 */
process.env.REACT_APP_BACKEND_URL = "http://127.0.0.1:8000";
import { describeDevice, executeDeviceTool, tvPowerRequestIsGrounded } from "../realtimeDeviceTools";

function ctx(lastUserText, overrides = {}) {
  return {
    resident_id: "res_test", room: "401", session_id: "rt_test",
    turn_suspect: false, last_user_text: lastUserText, ...overrides,
  };
}

// A single real TV in the room - toggle_tv now looks the device up first
// (2026-09-06 kiosk multi-light bug fix, applied generically to TVs too)
// so every test needs a device-list response, not just the command's.
const TV = { device_id: "dev_tv_test", kind: "tv", protocol: "ir_blaster", capabilities: ["power", "volume"], state: {} };

function commandCalls() {
  return global.fetch.mock.calls.filter(([url]) => String(url).includes("/command"));
}

beforeEach(() => {
  global.fetch = jest.fn(async (url, opts) => {
    if (String(url).includes("/devices/public/by-room/")) {
      return { ok: true, json: async () => [TV] };
    }
    const body = JSON.parse(opts.body);
    return { ok: true, json: async () => ({ verified: false, state: { [body.action]: body.value } }) };
  });
});

test("real incident: no TV command applies on ungrounded 'Hello Lab.'", async () => {
  const r = await executeDeviceTool({
    name: "toggle_tv", args: { state: "on", volume: 11 }, ctx: ctx("Hello Lab."),
  });
  expect(r.ok).toBe(false);
  expect(r.message).toContain("didn't hear a clear TV power or volume request");
  expect(commandCalls()).toHaveLength(0);
});

test.each([
  ["Hey, Aria.", "off"],
  ["Goodbye.", "off"],
  ["Turn it off.", "off"],
  ["Don't turn the TV off.", "off"],
  ["Do not switch on the television.", "on"],
  ["Turn the TV on.", "off"],
  ["Turn the TV off.", "on"],
])("wake, goodbye, ambiguous, negated and direction-mismatched speech sends no power: %s", async (text, state) => {
  const r = await executeDeviceTool({ name: "toggle_tv", args: { state }, ctx: ctx(text) });
  expect(r.ok).toBe(false);
  expect(commandCalls()).toHaveLength(0);
});

test.each([
  ["Can you turn the TV on?", "on"],
  ["Switch off the television.", "off"],
  ["Turn the television back on.", "on"],
  ["Shut the TV off.", "off"],
])("explicit direction-matched TV request is grounded: %s", (text, state) => {
  expect(tvPowerRequestIsGrounded(text, state)).toBe(true);
  expect(tvPowerRequestIsGrounded(text, state === "on" ? "off" : "on")).toBe(false);
});

test.each([
  "Turn the volume up.",
  "It's too loud.",
  "Can you make it quieter?",
  "Turn it down please.",
  "Mute it.",
])("genuine volume request still applies: %s", async (text) => {
  const r = await executeDeviceTool({
    name: "toggle_tv", args: { state: "on", volume: 20 }, ctx: ctx(text),
  });
  expect(r.ok).toBe(true);
  expect(r.message).toContain("sent the volume 20 command");
  const calls = commandCalls();
  expect(calls).toHaveLength(1);
  expect(JSON.parse(calls[0][1].body).action).toBe("volume");
  expect(calls.every(([, opts]) => JSON.parse(opts.body).device_id === "dev_tv_test")).toBe(true);
});

test("unverified infrared power result says sent, never turned", async () => {
  const r = await executeDeviceTool({
    name: "toggle_tv", args: { state: "on" }, ctx: ctx("Can you turn the TV on?"),
  });
  expect(r.ok).toBe(true);
  expect(r.message).toContain("sent the TV on command");
  expect(r.message).not.toContain("turned");
  expect(commandCalls()).toHaveLength(1);
});

test("verified state-reporting power result may say turned", async () => {
  global.fetch = jest.fn(async (url) => {
    if (String(url).includes("/devices/public/by-room/")) {
      return { ok: true, json: async () => [{ ...TV, protocol: "home_assistant" }] };
    }
    return { ok: true, json: async () => ({ verified: true, state: { power: "off" } }) };
  });
  const r = await executeDeviceTool({ name: "toggle_tv", args: { state: "off" }, ctx: ctx("Turn the TV off.") });
  expect(r.message).toBe("turned the TV off.");
});

test("device description never reports an infrared estimated volume as observed", () => {
  const ir = { ...TV, label: "Room 401 TV", room: "401", state: { power: "on", volume: 37, volume_estimated: true } };
  expect(describeDevice(ir)).toBe("the TV is on");
  expect(describeDevice(ir)).not.toContain("volume 37");
});

test("device description may report state-reporting TV volume", () => {
  const smart = { ...TV, label: "Room 401 TV", room: "401", protocol: "home_assistant", state: { power: "on", volume: 37 } };
  expect(describeDevice(smart)).toBe("the TV is on, volume 37");
});

test("two TVs in the room: toggle_tv fails closed instead of guessing", async () => {
  global.fetch = jest.fn(async (url) => {
    if (String(url).includes("/devices/public/by-room/")) {
      return { ok: true, json: async () => [TV, { ...TV, device_id: "dev_tv_test_2" }] };
    }
    return { ok: true, json: async () => ({ ok: true }) };
  });
  const r = await executeDeviceTool({ name: "toggle_tv", args: { state: "on" }, ctx: ctx("Turn the TV on.") });
  expect(r.ok).toBe(false);
  expect(r.message.toLowerCase()).toContain("more than one tv");
  expect(commandCalls()).toHaveLength(0);
});
