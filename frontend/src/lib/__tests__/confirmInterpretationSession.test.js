/**
 * RQ-025 B2: the confirm_interpretation_pattern tool sends the live
 * session_id (the server grounds the confirmation in it) and no longer sends
 * a client-chosen `source`.
 */
process.env.REACT_APP_BACKEND_URL = "http://127.0.0.1:8000";
import { executeOperationsTool } from "../realtimeOperationsTools";

beforeEach(() => {
  global.fetch = jest.fn(async () => ({ ok: true, json: async () => ({}) }));
});

test("confirm tool posts session_id and no source", async () => {
  const r = await executeOperationsTool({
    name: "confirm_interpretation_pattern",
    args: { heard_as: "dos savor", understood_as: "dos sabores", meaning: "two flavors" },
    ctx: { room: "T1", residentId: "res_1", sessionId: "rt_sess_9" },
  });
  expect(r.ok).toBe(true);
  const [url, opts] = global.fetch.mock.calls[0];
  expect(String(url)).toContain("/aria/interpretation-patterns/confirm");
  const body = JSON.parse(opts.body);
  expect(body.session_id).toBe("rt_sess_9");
  expect(body.resident_id).toBe("res_1");
  expect("source" in body).toBe(false);
});

test("a refused confirmation (403) is not reported as remembered", async () => {
  global.fetch = jest.fn(async () => ({ ok: false, status: 403, json: async () => ({}) }));
  const r = await executeOperationsTool({
    name: "confirm_interpretation_pattern",
    args: { heard_as: "x", understood_as: "y" },
    ctx: { room: "T1", residentId: "res_1", sessionId: "rt_sess_9" },
  });
  expect(r.message).not.toMatch(/remember/);
});
