/**
 * RQ-040: every device tool shares one ambiguity guard - structured refusal
 * once, then refused locally (no network) until a new resident utterance.
 */
process.env.REACT_APP_BACKEND_URL = "http://127.0.0.1:8000";
import { executeDeviceTool } from "../realtimeDeviceTools";
import { resetDeviceAmbiguity } from "../deviceAmbiguity";

const dev = (id, kind, label, extra = {}) => ({ device_id: id, kind, label: `Room 214 ${label}`, online: true, capabilities: ["power", "volume", "channel", "input", "position", "temperature"], inputs: ["HDMI 1"], state: { power: "on", volume: 20 }, ...extra });
const DEVICES = [
  dev("tv_a", "tv", "bedroom tv"), dev("tv_b", "tv", "den tv"),
  dev("th_a", "thermostat", "bedroom thermostat"), dev("th_b", "thermostat", "den thermostat"),
  dev("bl_a", "blinds", "east blinds"), dev("bl_b", "blinds", "west blinds"),
];
const ctx = (text, sid = "rt_amb") => ({ resident_id: "r", room: "214", session_id: sid, last_user_text: text });
const posts = () => global.fetch.mock.calls.filter(([u]) => String(u).includes("/command"));
const lookups = () => global.fetch.mock.calls.filter(([u]) => String(u).includes("by-room"));

beforeEach(() => {
  resetDeviceAmbiguity();
  global.fetch = jest.fn(async (url) => (String(url).includes("by-room")
    ? { ok: true, json: async () => DEVICES }
    : { ok: true, json: async () => ({ state: { power: "on", channel: 11, volume: 30, position: 100 } }) }));
});

const CASES = [
  ["toggle_tv", { state: "on" }, "turn the tv on", "TV"],
  ["set_tv_input", { input: "HDMI 1" }, "switch the input", "TV"],
  ["adjust_tv_volume", { direction: "up" }, "turn the volume up", "TV"],
  ["set_tv_channel", { channel: 11 }, "put on channel 11", "TV"],
  ["adjust_room_temperature", { target_f: 70 }, "set it to 70 degrees", "thermostat"],
  ["set_blinds", { action: "open" }, "open the blinds", "blinds"],
];

describe.each(CASES)("%s", (name, args, text, noun) => {
  test("refuses once with choices, then locally until a new utterance", async () => {
    const first = await executeDeviceTool({ name, args, ctx: ctx(text) });
    expect(first).toMatchObject({ ok: false, ambiguous: true });
    expect(first.choices).toHaveLength(2);
    expect(first.message).toContain(`more than one ${noun}`);
    expect(posts()).toHaveLength(0);
    const seen = global.fetch.mock.calls.length;
    for (let i = 0; i < 4; i++) {
      expect((await executeDeviceTool({ name, args, ctx: ctx(text) })).ambiguous).toBe(true);
    }
    expect(global.fetch.mock.calls.length).toBe(seen);
  });

  test("a new utterance naming the device goes through; another session is unaffected", async () => {
    await executeDeviceTool({ name, args, ctx: ctx(text) });
    const choice = (await executeDeviceTool({ name, args, ctx: ctx(text, "rt_other") })).choices[1];
    const label = DEVICES.find((d) => d.label.toLowerCase().endsWith(choice)).label;
    const r = await executeDeviceTool({ name, args: { ...args, device: label }, ctx: ctx(`${text}, the second one`) });
    expect(r.ambiguous).toBeUndefined();
    expect(posts().length).toBeGreaterThan(0);
  });
});

test("tool refusals are independent per tool in one session", async () => {
  await executeDeviceTool({ name: "toggle_tv", args: { state: "on" }, ctx: ctx("do it") });
  const blinds = await executeDeviceTool({ name: "set_blinds", args: { action: "open" }, ctx: ctx("open the blinds") });
  expect(blinds.ambiguous).toBe(true);
  expect(lookups().length).toBe(2);
});
