/**
 * call_for_help: Aria's wording must derive from the dispatch's ACTUAL
 * delivery state, never from having "tried" (Level 1 directive 2026-09-07,
 * Room 214 bleeding test).
 */
process.env.REACT_APP_BACKEND_URL = "http://127.0.0.1:8000";
import { executeDeviceTool } from "../realtimeDeviceTools";

const CTX = { room: "214", resident_id: "res_1", kiosk_id: "kio_1", alert_id: "alert_1", activation_id: "act_1", session_id: "rt_1" };
const ARGS = { reason: "resident reports bleeding at age 84", severity: "emergency" };

function mockFetch(status, body) {
  global.fetch = jest.fn(() => Promise.resolve({
    ok: status >= 200 && status < 300, status,
    json: () => Promise.resolve(body),
  }));
}
afterEach(() => { delete global.fetch; });

test("hits /alerts/ai-escalate with the open event's alert_id + activation_id (not /alerts)", async () => {
  mockFetch(200, { wording_state: "paged", dispatch: { status: "accepted" } });
  await executeDeviceTool({ name: "call_for_help", args: ARGS, ctx: CTX });
  const [url, opts] = global.fetch.mock.calls[0];
  expect(url).toMatch(/\/alerts\/ai-escalate$/);
  const b = JSON.parse(opts.body);
  expect(b).toMatchObject({
    reason: ARGS.reason, severity: "emergency", department: "Care/Nursing",
    alert_id: "alert_1", activation_id: "act_1", session_id: "rt_1",
  });
});

test("wording_state 'paged' -> Aria may say a nurse has been paged", async () => {
  mockFetch(200, { wording_state: "paged", dispatch: { status: "accepted" } });
  const r = await executeDeviceTool({ name: "call_for_help", args: ARGS, ctx: CTX });
  expect(r.ok).toBe(true);
  expect(r.message).toMatch(/nurse has been paged/i);
});

test("wording_state 'sent' -> 'sent your request to the care team', NOT 'paged'", async () => {
  mockFetch(200, { wording_state: "sent", dispatch: { status: "requested" } });
  const r = await executeDeviceTool({ name: "call_for_help", args: ARGS, ctx: CTX });
  expect(r.ok).toBe(true);
  expect(r.message).toMatch(/sent your request to the care team/i);
  expect(r.message).not.toMatch(/paged/i);
});

test("wording_state 'failed' -> must NOT claim anyone was paged; tell them the red button", async () => {
  mockFetch(200, { wording_state: "failed", dispatch: { status: "failed" } });
  const r = await executeDeviceTool({ name: "call_for_help", args: ARGS, ctx: CTX });
  expect(r.ok).toBe(false);
  expect(r.message).not.toMatch(/paged/i);
  expect(r.message).toMatch(/red button/i);
});

test("HTTP error -> no false success, points at the red button", async () => {
  mockFetch(502, {});
  const r = await executeDeviceTool({ name: "call_for_help", args: ARGS, ctx: CTX });
  expect(r.ok).toBe(false);
  expect(r.message).not.toMatch(/paged/i);
  expect(r.message).toMatch(/red button/i);
});
