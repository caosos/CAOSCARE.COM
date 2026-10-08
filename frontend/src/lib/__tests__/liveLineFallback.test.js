/**
 * RQ-031 (D1): when the live staff line cannot be used, the ask is filed
 * as a normal nursing request and the spoken result never implies anyone is
 * aware or on the way.
 */
process.env.REACT_APP_BACKEND_URL = "http://127.0.0.1:8000";
import { executeCareTool } from "../realtimeCareControl";

const ARRIVAL = /(on (the|their) way|coming|getting someone|headed|will be (there|here)|is aware|are aware)/i;

function setup({ ringOk = true, requestOk = true } = {}) {
  global.fetch = jest.fn(async (url) => {
    const u = String(url);
    if (u.includes("/live-line/ring")) return { ok: ringOk, json: async () => ({}) };
    if (u.includes("/tasks/resident-request")) {
      return requestOk
        ? { ok: true, status: 200, json: async () => ({ status: "pending", task_id: "task_1" }) }
        : { ok: false, status: 500, json: async () => ({}) };
    }
    return { ok: true, json: async () => ({ ok: true }) };
  });
}
const bodyOfRequest = () => {
  const call = global.fetch.mock.calls.find(([u]) => String(u).includes("/tasks/resident-request"));
  return call ? JSON.parse(call[1].body) : null;
};
const ctx = (text, extra = {}) => ({ room: "214", resident_id: "res_1", session_id: "s1", last_user_text: text, ...extra });

test("no open event: files a high-priority nursing request, no arrival wording", async () => {
  setup();
  const r = await executeCareTool({ name: "request_live_staff", args: {}, ctx: ctx("I need a nurse now") });
  const body = bodyOfRequest();
  expect(body.category).toBe("nursing");
  expect(body.priority).toBe("high");
  expect(body.resident_words).toBe("I need a nurse now");
  expect(r.ok).toBe(true);
  expect(r.filed).toBe(true);
  expect(r.message).toMatch(/sent a nursing request/);
  expect(r.message.replace(/can't tell you that anyone[^.]*\./, "")).not.toMatch(ARRIVAL);
});

test("non-urgent ask is filed at normal priority", async () => {
  setup();
  await executeCareTool({ name: "request_live_staff", args: {}, ctx: ctx("could a nurse stop by sometime") });
  expect(bodyOfRequest().priority).toBe("normal");
});

test("ring fails: falls back to filing instead of saying someone is coming", async () => {
  setup({ ringOk: false });
  const r = await executeCareTool({ name: "request_live_staff", args: {}, ctx: ctx("help me now", { alert_id: "a1" }) });
  expect(r.rang).toBe(false);
  expect(r.filed).toBe(true);
  expect(r.message).not.toMatch(/getting someone/i);
  expect(bodyOfRequest()).not.toBeNull();
});

test("filing also fails: ok false, says nothing was sent, no arrival wording", async () => {
  setup({ requestOk: false });
  const r = await executeCareTool({ name: "request_live_staff", args: {}, ctx: ctx("I need a nurse") });
  expect(r.ok).toBe(false);
  expect(r.message).toMatch(/Nothing was sent/);
  expect(r.message.replace(/can't tell you that anyone[^.]*\./, "")).not.toMatch(ARRIVAL);
});

test("ring succeeds: unchanged behavior, no extra request filed", async () => {
  setup();
  const r = await executeCareTool({ name: "request_live_staff", args: {}, ctx: ctx("help me now", { alert_id: "a1" }) });
  expect(r.rang).toBe(true);
  expect(bodyOfRequest()).toBeNull();
});
