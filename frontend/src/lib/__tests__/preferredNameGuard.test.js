/**
 * TSB-001 regression test (docs/tsb/TSB-001-resident-voice-name-attribution.md).
 * Reproduces the exact two live failures against the fix, per the TSB's own
 * "Verification Required" section, plus confirms genuine corrections still
 * work (the TSB's explicit stop-gate: a resident unable to correct their
 * own name is a worse failure than the one this TSB documents).
 */
process.env.REACT_APP_BACKEND_URL = "http://127.0.0.1:8000";
import { executeDeviceTool } from "../realtimeDeviceTools";

function ctx(lastUserText, overrides = {}) {
  return {
    resident_id: "res_test", room: "401", session_id: "rt_test",
    turn_suspect: false, last_user_text: lastUserText, ...overrides,
  };
}

beforeEach(() => {
  global.fetch = jest.fn(async () => ({ ok: true, json: async () => ({ ok: true }) }));
});

test("TSB-001 session 1 repro: 'Why do you call me Ellie?' must not fire the mutation", async () => {
  const r = await executeDeviceTool({
    name: "update_preferred_name",
    args: { preferred_name: "Eleanor" },
    ctx: ctx("Why do you call me Ellie?"),
  });
  expect(r.ok).toBe(false);
  expect(global.fetch).not.toHaveBeenCalled();
});

test("TSB-001 session 2 repro: 'Who told you to call me Ellie?' must not fire the mutation", async () => {
  const r = await executeDeviceTool({
    name: "update_preferred_name",
    args: { preferred_name: "Ellie" },
    ctx: ctx("Who told you to call me Ellie?"),
  });
  expect(r.ok).toBe(false);
  expect(global.fetch).not.toHaveBeenCalled();
});

test("genuine correction 'My name is Margaret, not Maggie' still saves", async () => {
  const r = await executeDeviceTool({
    name: "update_preferred_name",
    args: { preferred_name: "Margaret" },
    ctx: ctx("My name is Margaret, not Maggie."),
  });
  expect(r.ok).toBe(true);
  expect(global.fetch).toHaveBeenCalledTimes(1);
});

test("genuine correction 'Call me Mags' still saves", async () => {
  const r = await executeDeviceTool({
    name: "update_preferred_name",
    args: { preferred_name: "Mags" },
    ctx: ctx("Call me Mags."),
  });
  expect(r.ok).toBe(true);
  expect(global.fetch).toHaveBeenCalledTimes(1);
});

test("stale/missing transcript (no last_user_text) does not fire the mutation", async () => {
  const r = await executeDeviceTool({
    name: "update_preferred_name",
    args: { preferred_name: "Robert" },
    ctx: ctx(""),
  });
  expect(r.ok).toBe(false);
  expect(global.fetch).not.toHaveBeenCalled();
});

test("existing echo/turn_suspect guard still takes priority over the new check", async () => {
  const r = await executeDeviceTool({
    name: "update_preferred_name",
    args: { preferred_name: "Margaret" },
    ctx: ctx("My name is Margaret, not Maggie.", { turn_suspect: true, turn_suspect_reason: "echo_like" }),
  });
  expect(r.ok).toBe(false);
  expect(global.fetch).not.toHaveBeenCalled();
});
