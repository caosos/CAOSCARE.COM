/**
 * RQ-021: blinds, TV channel and TV volume-step tools, and the demo room's
 * staff-notified chips. Same grounding rule as the other device tools:
 * nothing is sent unless the resident's own words support it, and the spoken
 * result comes from the state the backend read back.
 */
process.env.REACT_APP_BACKEND_URL = "http://127.0.0.1:8000";
import { executeDeviceTool } from "../realtimeDeviceTools";
import { numbersIn } from "../realtimeRoomControls";
import { staffNotifiedChips, demoRoomView } from "../demoRoom";

const ctx = (heard, extra = {}) => ({ resident_id: "r", room: "DEMO", session_id: "rt_x", turn_suspect: false, last_user_text: heard, ...extra });
const BLINDS = { device_id: "d_bl", kind: "blinds", capabilities: ["position"], state: { position: 0 } };
const TV = { device_id: "d_tv", kind: "tv", capabilities: ["power", "volume", "channel", "input"], state: { power: "on", volume: 20, channel: 3 } };
let devices;
let commandReply;

const commands = () => global.fetch.mock.calls.filter(([u]) => String(u).includes("/command")).map(([, o]) => JSON.parse(o.body));

beforeEach(() => {
  devices = [BLINDS, TV];
  commandReply = (body) => ({ ok: true, json: async () => ({ simulated: true, verified: true, state: { [body.action]: body.value } }) });
  global.fetch = jest.fn(async (url, opts) => {
    if (String(url).includes("/devices/public/by-room/")) return { ok: true, json: async () => devices };
    return commandReply(JSON.parse(opts.body));
  });
});

test("numbersIn reads digits and spoken numbers", () => {
  expect([...numbersIn("channel 11")]).toEqual([11]);
  expect(numbersIn("put on channel twenty one").has(21)).toBe(true);
  expect(numbersIn("channel eleven").has(11)).toBe(true);
  expect(numbersIn("hello").size).toBe(0);
});

describe("set_blinds", () => {
  test("open sends position 100 and speaks the read-back, labelled simulated", async () => {
    const r = await executeDeviceTool({ name: "set_blinds", args: { action: "open" }, ctx: ctx("Open the blinds please") });
    expect(r).toEqual({ ok: true, message: "the blinds are now fully open (simulated device)." });
    expect(commands()).toEqual([expect.objectContaining({ action: "position", value: 100, kind: "blinds", device_id: "d_bl", session_id: "rt_x" })]);
  });
  test("close and set a percent", async () => {
    await executeDeviceTool({ name: "set_blinds", args: { action: "close" }, ctx: ctx("close the shades") });
    const r = await executeDeviceTool({ name: "set_blinds", args: { action: "set", percent: 40 }, ctx: ctx("set the blinds to forty percent") });
    expect(commands().map((c) => c.value)).toEqual([0, 40]);
    expect(r.message).toContain("40% open");
  });
  test("a turn that never mentioned blinds sends nothing", async () => {
    const r = await executeDeviceTool({ name: "set_blinds", args: { action: "open" }, ctx: ctx("Hello Lab.") });
    expect(r.ok).toBe(false);
    expect(commands()).toHaveLength(0);
  });
  test("room without blinds, or a device that cannot move: honest, nothing sent", async () => {
    devices = [TV];
    const none = await executeDeviceTool({ name: "set_blinds", args: { action: "open" }, ctx: ctx("open the blinds") });
    expect(none).toEqual({ ok: false, message: "there's no blinds set up in this room." });
    devices = [{ ...BLINDS, capabilities: [] }];
    const fixed = await executeDeviceTool({ name: "set_blinds", args: { action: "open" }, ctx: ctx("open the blinds") });
    expect(fixed.ok).toBe(false);
    expect(commands()).toHaveLength(0);
  });
  test("a rejected command is reported, never claimed", async () => {
    commandReply = () => ({ ok: false, status: 502, json: async () => ({ detail: "device is offline" }) });
    const r = await executeDeviceTool({ name: "set_blinds", args: { action: "open" }, ctx: ctx("open the blinds") });
    expect(r.ok).toBe(false);
    expect(r.message).toContain("device is offline");
  });
  test("an answer with no state is not success", async () => {
    commandReply = () => ({ ok: true, json: async () => ({}) });
    const r = await executeDeviceTool({ name: "set_blinds", args: { action: "open" }, ctx: ctx("open the blinds") });
    expect(r.ok).toBe(false);
  });
  test("suspect turn is refused", async () => {
    const r = await executeDeviceTool({ name: "set_blinds", args: { action: "open" }, ctx: ctx("open the blinds", { turn_suspect: true }) });
    expect(r.ok).toBe(false);
    expect(commands()).toHaveLength(0);
  });
});

describe("set_tv_channel", () => {
  test("grounded channel is sent and read back", async () => {
    const r = await executeDeviceTool({ name: "set_tv_channel", args: { channel: 11 }, ctx: ctx("Put on channel 11") });
    expect(r.message).toBe("the TV is on channel 11 (simulated device).");
    expect(commands()).toEqual([expect.objectContaining({ action: "channel", value: 11, device_id: "d_tv" })]);
  });
  test("spoken number words count", async () => {
    const r = await executeDeviceTool({ name: "set_tv_channel", args: { channel: 11 }, ctx: ctx("change to channel eleven") });
    expect(r.ok).toBe(true);
  });
  test("the 'Hello Lab' class: no channel word or a different number sends nothing", async () => {
    for (const heard of ["Hello Lab.", "Put on channel 5", "eleven"]) {
      const r = await executeDeviceTool({ name: "set_tv_channel", args: { channel: 11 }, ctx: ctx(heard) });
      expect(r.ok).toBe(false);
    }
    expect(commands()).toHaveLength(0);
  });
  test("TV that is off is turned on first and says so", async () => {
    devices = [BLINDS, { ...TV, state: { power: "off" } }];
    const r = await executeDeviceTool({ name: "set_tv_channel", args: { channel: 7 }, ctx: ctx("channel 7 please") });
    expect(commands().map((c) => c.action)).toEqual(["power", "channel"]);
    expect(r.message).toMatch(/^turned the TV on and /);
  });
  test("TV without a channel capability: honest, nothing sent", async () => {
    devices = [{ ...TV, capabilities: ["power", "volume"] }];
    const r = await executeDeviceTool({ name: "set_tv_channel", args: { channel: 7 }, ctx: ctx("channel 7") });
    expect(r).toEqual({ ok: false, message: "this TV doesn't have channel control." });
    expect(commands()).toHaveLength(0);
  });
});

describe("adjust_tv_volume", () => {
  test("up and down by a step from the device's own volume", async () => {
    const up = await executeDeviceTool({ name: "adjust_tv_volume", args: { direction: "up" }, ctx: ctx("Turn the volume up") });
    expect(up.message).toBe("the TV volume is now 30 (simulated device).");
    await executeDeviceTool({ name: "adjust_tv_volume", args: { direction: "down", amount: 5 }, ctx: ctx("a bit quieter") });
    expect(commands().map((c) => c.value)).toEqual([30, 15]);
  });
  test("clamped at 0 and 100", async () => {
    devices = [{ ...TV, state: { power: "on", volume: 95 } }];
    await executeDeviceTool({ name: "adjust_tv_volume", args: { direction: "up" }, ctx: ctx("louder") });
    expect(commands()[0].value).toBe(100);
  });
  test("no volume words: nothing sent", async () => {
    const r = await executeDeviceTool({ name: "adjust_tv_volume", args: { direction: "up" }, ctx: ctx("Hello Lab.") });
    expect(r.ok).toBe(false);
    expect(commands()).toHaveLength(0);
  });
  test("TV off: no volume change, honest message", async () => {
    devices = [{ ...TV, state: { power: "off" } }];
    const r = await executeDeviceTool({ name: "adjust_tv_volume", args: { direction: "up" }, ctx: ctx("turn it up") });
    expect(r.ok).toBe(false);
    expect(commands()).toHaveLength(0);
  });
});

describe("demo room staff chips", () => {
  const req = (o) => ({ task_id: "t1", category: "maintenance", what_for: "My sink is leaking", status: "pending", is_open: true, acknowledged: false, ...o });
  test("only real open requests make a chip, worded by their real stage", () => {
    expect(staffNotifiedChips([])).toEqual([]);
    expect(staffNotifiedChips(null)).toEqual([]);
    expect(staffNotifiedChips([req()])[0].label).toBe("Staff notified: My sink is leaking");
    expect(staffNotifiedChips([req({ acknowledged: true })])[0].label).toBe("Staff have seen it: My sink is leaking");
    expect(staffNotifiedChips([req({ status: "in_progress", acknowledged: true })])[0].label).toBe("Staff are working on it: My sink is leaking");
    expect(staffNotifiedChips([req({ status: "completed", is_open: false }), req({ status: "skipped", is_open: false })])).toEqual([]);
  });
  test("no chip ever promises arrival", () => {
    const all = staffNotifiedChips([req(), req({ acknowledged: true }), req({ status: "in_progress" })]);
    all.forEach((c) => expect(c.label).not.toMatch(/on the way|coming|headed/i));
  });
  test("blinds view still reads the device store", () => {
    expect(demoRoomView([{ kind: "blinds", state: { position: 60 }, online: true }]).blinds.position).toBe(60);
  });
});
