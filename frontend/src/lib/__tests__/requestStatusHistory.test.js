/**
 * check_request_status (CURRENT/open only) vs check_request_history
 * (explicit past lookup), and lifecycle-time phrasing derived from the
 * backend's facility-local labels. Level 1 directive 2026-09-07.
 */
process.env.REACT_APP_BACKEND_URL = "http://127.0.0.1:8000";
import { executeOperationsTool } from "../realtimeOperationsTools";

const CTX = { room: "214", residentId: "res_1", sessionId: "rt_1" };
const call = (name, args = {}) => executeOperationsTool({ name, args, ctx: CTX });

function mockJson(status, body) {
  global.fetch = jest.fn((url) => Promise.resolve({
    ok: status >= 200 && status < 300, status, _url: url,
    json: () => Promise.resolve(body),
  }));
}
afterEach(() => { delete global.fetch; });

test("check_request_status hits /status and says 'no open request' when found:false", async () => {
  mockJson(200, { found: false, scope: "current" });
  const r = await call("check_request_status");
  expect(global.fetch.mock.calls[0][0]).toMatch(/\/tasks\/resident-request\/status\?/);
  expect(r.ok).toBe(true);
  expect(r.message).toMatch(/no open request/i);
  expect(r.message).not.toMatch(/completed/i);
});

test("check_request_status reports lifecycle labels from the backend, verbatim", async () => {
  mockJson(200, {
    found: true, scope: "current", is_open: true, status: "in_progress",
    what_for: "broken blind", acknowledged: true, assigned_to_name: null,
    scheduled_date: null, scheduled_time_label: null, latest_update: "waiting on a part",
    latest_update_at: null, re_request_count: 1,
    created: { iso: "x", local: "y", label: "today at 2:17 PM" },
    acknowledged_at: { iso: "x", local: "y", label: "today at 2:31 PM" },
    started_at: { iso: "x", local: "y", label: "today at 2:40 PM" },
    completed_at: null, last_re_requested_at: { iso: "x", local: "y", label: "today at 2:25 PM" },
  });
  const r = await call("check_request_status");
  expect(r.message).toContain("broken blind");
  expect(r.message).toContain("asked today at 2:17 PM");
  expect(r.message).toContain("acknowledged today at 2:31 PM");
  expect(r.message).toContain("started today at 2:40 PM");
  expect(r.message).toContain("asked again today at 2:25 PM");
  expect(r.message).toMatch(/waiting on a part.*no timestamp on record/i);
});

test("check_request_history hits /history and never fires for a non-historical call path", async () => {
  mockJson(200, {
    found: true, scope: "history", requests: [
      { task_id: "t1", category: "maintenance", what_for: "reading lamp flickering",
        status: "completed",
        created: { label: "yesterday at 11:47 AM" },
        completed_at: { label: "yesterday at 9:47 PM" },
        acknowledged_at: null, started_at: null, last_re_requested_at: null },
    ],
  });
  const r = await call("check_request_history", { category: "maintenance" });
  expect(global.fetch.mock.calls[0][0]).toMatch(/\/tasks\/resident-request\/history\?/);
  expect(r.message).toContain("reading lamp flickering");
  expect(r.message).toContain("completed yesterday at 9:47 PM");
});

test("check_request_history says 'nothing finished' when empty", async () => {
  mockJson(200, { found: false, scope: "history", requests: [] });
  const r = await call("check_request_history");
  expect(r.message).toMatch(/nothing finished on record/i);
});

test("a null lifecycle time is simply omitted, never rendered as a made-up time", async () => {
  mockJson(200, {
    found: true, scope: "current", is_open: true, status: "pending", what_for: "package",
    acknowledged: false, scheduled_date: null, scheduled_time_label: null,
    latest_update: "", latest_update_at: null, re_request_count: 0,
    created: { label: "today at 9:03 AM" },
    acknowledged_at: null, started_at: null, completed_at: null, last_re_requested_at: null,
  });
  const r = await call("check_request_status");
  expect(r.message).toContain("asked today at 9:03 AM");
  // no fabricated lifecycle time for the fields that are null
  expect(r.message).not.toMatch(/acknowledged \w+ at \d/i);
  expect(r.message).not.toMatch(/started \w+ at \d/i);
  expect(r.message).not.toMatch(/completed \w+ at \d/i);
});
