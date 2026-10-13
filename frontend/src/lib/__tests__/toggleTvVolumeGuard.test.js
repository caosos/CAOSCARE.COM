/**
 * Regression test for the toggle_tv volume grounding guard
 * (docs/PROJECT_STATE.md, 2026-08-30 incident). Reproduces the exact live
 * failure: the transcript "Hello Lab" (garbled/nonsense) led the model to
 * call toggle_tv(state="on", volume=11) - the 11 wasn't grounded in
 * anything the resident's saved transcript actually says. The combined
 * command is refused before either power or volume changes.
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
const TV = { device_id: "dev_tv_test", kind: "tv", protocol: "home_assistant", endpoint: "media_player.test_tv", capabilities: ["power", "volume"], state: { power: "on", volume: 35 } };

function commandCalls() {
  return global.fetch.mock.calls.filter(([url]) => String(url).includes("/command"));
}

beforeEach(() => {
  global.fetch = jest.fn(async (url, opts) => {
    if (String(url).includes("/devices/public/by-room/")) {
      return { ok: true, json: async () => [TV] };
    }
    const body = JSON.parse(opts.body);
    return { ok: true, json: async () => ({ ok: true, verified: true, state: { [body.action]: body.value } }) };
  });
});

test("real incident: toggle_tv volume must NOT apply on 'Hello Lab.'", async () => {
  const r = await executeDeviceTool({
    name: "toggle_tv", args: { state: "on", volume: 11 }, ctx: ctx("Hello Lab."),
  });
  expect(r.ok).toBe(false);
  expect(commandCalls()).toHaveLength(0);
});

test.each(["Set the volume to 20.", "Turn the TV on at volume twenty."])("explicit grounded volume request applies: %s", async (text) => {
  const r = await executeDeviceTool({
    name: "toggle_tv", args: { state: "on", volume: 20 }, ctx: ctx(text),
  });
  expect(r.ok).toBe(true);
  expect(r.message).toBe('turned the TV on and kept it lower while we talk. Ask the resident, "Is that good?"');
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
