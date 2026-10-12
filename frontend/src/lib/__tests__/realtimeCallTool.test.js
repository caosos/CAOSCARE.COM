// call_contact speaks only the backend's answer; a failure never becomes "calling".
jest.mock("../api", () => ({ API: "http://api.test/api" }));
import { executeCallTool } from "../realtimeCallTool";

beforeEach(() => { global.fetch = jest.fn(); });

test("other tools are not handled here", async () => {
  expect(await executeCallTool({ name: "get_menu", args: {}, ctx: {} })).toBeNull();
});

test("posts the target with the session identity and returns the backend wording", async () => {
  global.fetch.mockResolvedValue({ ok: true, json: () => Promise.resolve({ ok: false, outcome: "not_configured", message: "Calling isn't set up here yet, so I can't call the front desk." }) });
  const r = await executeCallTool({ name: "call_contact", args: { target: "front desk" }, ctx: { residentId: "r1", sessionId: "s1" } });
  const [url, opts] = global.fetch.mock.calls[0];
  expect(url).toBe("http://api.test/api/telephony/room-call-request");
  expect(JSON.parse(opts.body)).toEqual({ target: "front desk", resident_id: "r1", session_id: "s1" });
  expect(r).toEqual({ ok: false, outcome: "not_configured", message: "Calling isn't set up here yet, so I can't call the front desk." });
});

test("a refused or failed request never claims a call", async () => {
  global.fetch.mockResolvedValue({ ok: false, json: () => Promise.resolve({ detail: "nope" }) });
  const r = await executeCallTool({ name: "call_contact", args: { target: "Liam" }, ctx: {} });
  expect(r.ok).toBe(false);
  expect(r.message).not.toMatch(/calling|ringing|answered/i);
  global.fetch.mockRejectedValue(new Error("down"));
  expect((await executeCallTool({ name: "call_contact", args: { target: "Liam" }, ctx: {} })).ok).toBe(false);
});
