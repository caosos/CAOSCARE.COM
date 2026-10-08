/**
 * toggle_light coverage for the real Matter light-control work
 * (docs/PROJECT_STATE.md, 2026-09-05): color/color_temp/brightness_delta,
 * implicit power-on, capability gating, and the conversational-reference
 * case ("make it green" then "now dim it" then "turn it off" - each turn
 * only needs to name what changed, not repeat the whole state).
 */
process.env.REACT_APP_BACKEND_URL = "http://127.0.0.1:8000";
import { executeDeviceTool } from "../realtimeDeviceTools";

function ctx(overrides = {}) {
  return { resident_id: "res_test", room: "214", session_id: "rt_test", turn_suspect: false, ...overrides };
}

function mockFetch(light) {
  global.fetch = jest.fn(async (url) => {
    if (String(url).includes("/devices/public/by-room/")) {
      return { ok: true, json: async () => [light] };
    }
    return { ok: true, json: async () => ({ ok: true }) };
  });
}

const LIGHT_OFF = { device_id: "dev_light", kind: "light", capabilities: ["power", "brightness", "color", "color_temp"], state: {} };
const LIGHT_ON_DIM = { device_id: "dev_light", kind: "light", capabilities: ["power", "brightness", "color", "color_temp"], state: { power: "on", brightness: 60 } };
const LIGHT_BASIC = { device_id: "dev_light", kind: "light", capabilities: ["power", "brightness"], state: { power: "on" } };

test("'make it green' on an OFF light: implies power on, then sets color", async () => {
  mockFetch(LIGHT_OFF);
  const r = await executeDeviceTool({ name: "toggle_light", args: { color: "green" }, ctx: ctx() });
  expect(r.ok).toBe(true);
  expect(r.message).toContain("green");
  const posts = global.fetch.mock.calls.filter(([u]) => String(u).includes("/command"));
  expect(posts).toHaveLength(2);
  expect(JSON.parse(posts[0][1].body)).toMatchObject({ action: "power", value: "on" });
  expect(JSON.parse(posts[1][1].body)).toMatchObject({ action: "color", value: [0, 200, 0] });
});

test("'make it green' on an ALREADY-ON light: no redundant power command", async () => {
  mockFetch(LIGHT_ON_DIM);
  const r = await executeDeviceTool({ name: "toggle_light", args: { color: "green" }, ctx: ctx() });
  expect(r.ok).toBe(true);
  const posts = global.fetch.mock.calls.filter(([u]) => String(u).includes("/command"));
  expect(posts).toHaveLength(1);
  expect(JSON.parse(posts[0][1].body)).toMatchObject({ action: "color" });
});

test("conversational follow-up: 'now make it dimmer' resolves relative to current brightness", async () => {
  mockFetch(LIGHT_ON_DIM); // brightness: 60
  const r = await executeDeviceTool({ name: "toggle_light", args: { brightness_delta: -20 }, ctx: ctx() });
  expect(r.ok).toBe(true);
  expect(r.message).toContain("40 percent");
  const posts = global.fetch.mock.calls.filter(([u]) => String(u).includes("/command"));
  expect(posts).toHaveLength(1);
  expect(JSON.parse(posts[0][1].body)).toMatchObject({ action: "brightness", value: 40 });
});

test("conversational follow-up: 'turn it off' needs no other fields", async () => {
  mockFetch(LIGHT_ON_DIM);
  const r = await executeDeviceTool({ name: "toggle_light", args: { state: "off" }, ctx: ctx() });
  expect(r.ok).toBe(true);
  expect(r.message).toBe("turned the light off.");
});

test("'set it to 50 percent' sends an absolute brightness, not relative", async () => {
  mockFetch(LIGHT_ON_DIM);
  const r = await executeDeviceTool({ name: "toggle_light", args: { brightness: 50 }, ctx: ctx() });
  const posts = global.fetch.mock.calls.filter(([u]) => String(u).includes("/command"));
  expect(JSON.parse(posts[0][1].body)).toMatchObject({ action: "brightness", value: 50 });
});

test("'make it warm white' maps to the warm color_temp Kelvin value", async () => {
  mockFetch(LIGHT_ON_DIM);
  const r = await executeDeviceTool({ name: "toggle_light", args: { color_temp: "warm" }, ctx: ctx() });
  expect(r.message).toContain("warm white");
  const posts = global.fetch.mock.calls.filter(([u]) => String(u).includes("/command"));
  expect(JSON.parse(posts[0][1].body)).toMatchObject({ action: "color_temp", value: 2700 });
});

test("unsupported capability (color on a basic light) is reported honestly, not silently dropped", async () => {
  mockFetch(LIGHT_BASIC); // no color/color_temp capability
  const r = await executeDeviceTool({ name: "toggle_light", args: { color: "blue" }, ctx: ctx() });
  expect(r.ok).toBe(false); // SC-10: nothing the resident asked for happened
  expect(r.unsupported).toEqual(["color"]);
  expect(r.message).toContain("doesn't support color");
  const posts = global.fetch.mock.calls.filter(([u]) => String(u).includes("/command"));
  expect(posts).toHaveLength(0); // never sent a color command the device can't do
});

// SC-10 (Lane G demo 2026-09-28): "make the light green" on an OFF light
// without color switched it on, then reported "doesn't support color" with
// ok:true. Capability is now checked first; nothing is sent.
const LIGHT_BASIC_OFF = { device_id: "dev_light", kind: "light", capabilities: ["power", "brightness"], state: { power: "off", brightness: 80 } };

test("SC-10: unsupported color on an OFF light sends no power-on and no command at all", async () => {
  mockFetch(LIGHT_BASIC_OFF);
  const r = await executeDeviceTool({ name: "toggle_light", args: { color: "green" }, ctx: ctx() });
  expect(r.ok).toBe(false);
  expect(r.message).toContain("doesn't support color");
  expect(r.message).toContain("left it as it was");
  expect(r.message).not.toMatch(/turned|set the/);
  const posts = global.fetch.mock.calls.filter(([u]) => String(u).includes("/command"));
  expect(posts).toHaveLength(0);
});

test("SC-10: a supported + unsupported mix (brightness + color temperature) changes nothing", async () => {
  mockFetch(LIGHT_BASIC_OFF);
  const r = await executeDeviceTool({ name: "toggle_light", args: { state: "on", brightness: 40, color_temp: "warm" }, ctx: ctx() });
  expect(r.ok).toBe(false);
  expect(r.unsupported).toEqual(["color temperature"]);
  const posts = global.fetch.mock.calls.filter(([u]) => String(u).includes("/command"));
  expect(posts).toHaveLength(0);
});

test("SC-10: supported attributes on an OFF light still imply power-on (unchanged)", async () => {
  mockFetch(LIGHT_BASIC_OFF);
  const r = await executeDeviceTool({ name: "toggle_light", args: { brightness: 40 }, ctx: ctx() });
  expect(r.ok).toBe(true);
  const posts = global.fetch.mock.calls.filter(([u]) => String(u).includes("/command"));
  expect(posts.map(([, o]) => JSON.parse(o.body).action)).toEqual(["power", "brightness"]);
});

test("no room context is rejected before any network call", async () => {
  global.fetch = jest.fn();
  const r = await executeDeviceTool({ name: "toggle_light", args: { color: "red" }, ctx: ctx({ room: null }) });
  expect(r.ok).toBe(false);
  expect(global.fetch).not.toHaveBeenCalled();
});

test("empty args (nothing to change) is rejected before any network call", async () => {
  global.fetch = jest.fn();
  const r = await executeDeviceTool({ name: "toggle_light", args: {}, ctx: ctx() });
  expect(r.ok).toBe(false);
  expect(global.fetch).not.toHaveBeenCalled();
});

// Two real lights in one room (Room 214's desk + overhead bulbs, both
// kind="light") - proves disambiguation-by-name and exact device_id
// targeting, not just "there happens to be one light" (2026-09-05, real
// second-bulb work).
const DESK = { device_id: "dev_desk", kind: "light", label: "Room 214 desk lamp", capabilities: ["power", "brightness", "color", "color_temp"], state: { power: "on" } };
const OVERHEAD = { device_id: "dev_overhead", kind: "light", label: "Room 214 overhead light", capabilities: ["power", "brightness", "color", "color_temp"], state: { power: "on" } };

function mockFetchMulti(lights) {
  global.fetch = jest.fn(async (url) => {
    if (String(url).includes("/devices/public/by-room/")) {
      return { ok: true, json: async () => lights };
    }
    return { ok: true, json: async () => ({ ok: true }) };
  });
}

test("'turn off the desk light' with two lights present targets the desk lamp by device_id", async () => {
  mockFetchMulti([DESK, OVERHEAD]);
  const r = await executeDeviceTool({
    name: "toggle_light", args: { state: "off" }, ctx: ctx({ last_user_text: "turn off the desk light" }),
  });
  expect(r.ok).toBe(true);
  expect(r.message).toContain("desk");
  const posts = global.fetch.mock.calls.filter(([u]) => String(u).includes("/command"));
  expect(posts).toHaveLength(1);
  expect(JSON.parse(posts[0][1].body)).toMatchObject({ action: "power", device_id: "dev_desk" });
});

test("'make the overhead light green' targets the overhead bulb by device_id", async () => {
  mockFetchMulti([DESK, OVERHEAD]);
  const r = await executeDeviceTool({
    name: "toggle_light", args: { color: "green" }, ctx: ctx({ last_user_text: "make the overhead light green" }),
  });
  expect(r.ok).toBe(true);
  const posts = global.fetch.mock.calls.filter(([u]) => String(u).includes("/command"));
  expect(posts.every(([, opts]) => JSON.parse(opts.body).device_id === "dev_overhead")).toBe(true);
});

test("'turn the light off' with two lights and no distinguishing word asks for clarification, sends nothing", async () => {
  mockFetchMulti([DESK, OVERHEAD]);
  const r = await executeDeviceTool({
    name: "toggle_light", args: { state: "off" }, ctx: ctx({ last_user_text: "turn the light off" }),
  });
  expect(r.ok).toBe(false);
  expect(r.message.toLowerCase()).toContain("more than one light");
  const posts = global.fetch.mock.calls.filter(([u]) => String(u).includes("/command"));
  expect(posts).toHaveLength(0);
});

// RQ-038: light retry storm (session rt_lgjc64m9: 16 refused calls in 8 s).
describe("ambiguity refusal does not loop", () => {
  const { resetLightAmbiguity } = require("../realtimeLightControl");
  beforeEach(() => resetLightAmbiguity());
  const call = (args, text, sid = "rt_amb") =>
    executeDeviceTool({ name: "toggle_light", args, ctx: ctx({ session_id: sid, last_user_text: text }) });

  test("structured refusal; the same utterance is refused locally without the network", async () => {
    mockFetchMulti([DESK, OVERHEAD]);
    const first = await call({ state: "on" }, "turn the light on");
    expect(first).toMatchObject({ ok: false, ambiguous: true, choices: ["desk lamp", "overhead light"] });
    const calls = global.fetch.mock.calls.length;
    for (let i = 0; i < 5; i++) {
      const again = await call({ state: "on" }, "turn the light on");
      expect(again.ambiguous).toBe(true);
    }
    expect(global.fetch.mock.calls.length).toBe(calls);
  });

  test("a new utterance naming the light goes through (by words, or by device argument)", async () => {
    mockFetchMulti([DESK, OVERHEAD]);
    await call({ state: "on" }, "turn the light on");
    const r = await call({ state: "on", device: "Overhead Light" }, "the overhead one");
    expect(r.ok).toBe(true);
    const posts = global.fetch.mock.calls.filter(([u]) => String(u).includes("/command"));
    expect(JSON.parse(posts[0][1].body).device_id).toBe("dev_overhead");
    await call({ state: "on" }, "turn the light on");
    const byId = await call({ state: "off", device: "dev_desk" }, "desk lamp please");
    expect(byId.ok).toBe(true);
  });

  test("another session is not blocked by this one's refusal", async () => {
    mockFetchMulti([DESK, OVERHEAD]);
    await call({ state: "on" }, "turn the light on", "rt_a");
    const other = await call({ state: "on" }, "turn the light on", "rt_b");
    expect(other.ambiguous).toBe(true);
    expect(global.fetch.mock.calls.filter(([u]) => String(u).includes("by-room")).length).toBe(2);
  });
});
