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
  expect(r.ok).toBe(true); // the call itself succeeded, just not that field
  expect(r.message).toContain("doesn't support color");
  const posts = global.fetch.mock.calls.filter(([u]) => String(u).includes("/command"));
  expect(posts).toHaveLength(0); // never sent a color command the device can't do
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
