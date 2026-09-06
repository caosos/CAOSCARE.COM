/**
 * Regression test for the toggle_tv volume grounding guard
 * (docs/PROJECT_STATE.md, 2026-08-30 incident). Reproduces the exact live
 * failure: the transcript "Hello Lab" (garbled/nonsense) led the model to
 * call toggle_tv(state="on", volume=11) - the 11 wasn't grounded in
 * anything the resident's saved transcript actually says. Power itself is
 * still applied (a real, already-on-topic request), only the ungrounded
 * volume change is withheld.
 */
process.env.REACT_APP_BACKEND_URL = "http://127.0.0.1:8000";
import { executeDeviceTool } from "../realtimeDeviceTools";

function ctx(lastUserText, overrides = {}) {
  return {
    resident_id: "res_test", room: "401", session_id: "rt_test",
    turn_suspect: false, last_user_text: lastUserText, ...overrides,
  };
}

// A single real TV in the room - toggle_tv now looks the device up first
// (2026-09-06 kiosk multi-light bug fix, applied generically to TVs too)
// so every test needs a device-list response, not just the command's.
const TV = { device_id: "dev_tv_test", kind: "tv", capabilities: ["power", "volume"], state: {} };

function commandCalls() {
  return global.fetch.mock.calls.filter(([url]) => String(url).includes("/command"));
}

beforeEach(() => {
  global.fetch = jest.fn(async (url) => {
    if (String(url).includes("/devices/public/by-room/")) {
      return { ok: true, json: async () => [TV] };
    }
    return { ok: true, json: async () => ({ ok: true }) };
  });
});

test("real incident: toggle_tv volume must NOT apply on 'Hello Lab.'", async () => {
  const r = await executeDeviceTool({
    name: "toggle_tv", args: { state: "on", volume: 11 }, ctx: ctx("Hello Lab."),
  });
  expect(r.ok).toBe(true);
  expect(r.message).toBe("turned the TV on.");
  // power command sent, volume command must not have been
  const calls = commandCalls();
  expect(calls).toHaveLength(1);
  expect(JSON.parse(calls[0][1].body)).toMatchObject({ action: "power", device_id: "dev_tv_test" });
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
  expect(r.message).toBe("turned the TV on at volume 20.");
  const calls = commandCalls();
  expect(calls).toHaveLength(2);
  expect(calls.every(([, opts]) => JSON.parse(opts.body).device_id === "dev_tv_test")).toBe(true);
});

test("power-only request (no volume arg) is unaffected", async () => {
  const r = await executeDeviceTool({
    name: "toggle_tv", args: { state: "on" }, ctx: ctx("Can you turn the TV on?"),
  });
  expect(r.ok).toBe(true);
  expect(r.message).toBe("turned the TV on.");
  expect(commandCalls()).toHaveLength(1);
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
