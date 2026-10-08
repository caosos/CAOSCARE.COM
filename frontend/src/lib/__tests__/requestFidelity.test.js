import { executeOperationsTool } from "../realtimeOperationsTools";
import { literalResidentWords, openRequestsMessage } from "../requestOverview";

const json = (body, status = 200) => ({ ok: status < 400, status, json: async () => body });
afterEach(() => { global.fetch = undefined; });

test("literal words: long utterance kept, confirmations dropped", () => {
  expect(literalResidentWords({ last_user_text: "Something smells strange in my bathroom." }))
    .toBe("Something smells strange in my bathroom.");
  expect(literalResidentWords({ last_user_text: "yes please" })).toBeNull();
  expect(literalResidentWords({})).toBeNull();
});

test("request_staff_help sends the resident's sentence as resident_words, summary apart", async () => {
  let sent;
  global.fetch = jest.fn(async (url, opts) => { sent = JSON.parse(opts.body); return json({ status: "pending", task_id: "t1" }); });
  await executeOperationsTool({
    name: "request_staff_help",
    args: { category: "maintenance", summary: "bathroom odor" },
    ctx: { room: "1", residentId: "r1", sessionId: "s1", last_user_text: "Something smells strange in my bathroom." },
  });
  expect(sent.resident_words).toBe("Something smells strange in my bathroom.");
  expect(sent.summary).toBe("bathroom odor");
});

test("a past-date refusal is asked as the backend wrote it", async () => {
  global.fetch = jest.fn(async () => json({ detail: { needs_clarification: true, ask: "That date, October 5, has already passed. Which date and month do you mean?" } }, 422));
  const out = await executeOperationsTool({
    name: "request_transportation",
    args: { purpose: "doctor", requested_for_date: "2026-10-05" },
    ctx: { room: "1", residentId: "r1", sessionId: "s1" },
  });
  expect(out.ok).toBe(false);
  expect(out.message).toMatch(/already passed. Which date and month/);
});

test("openRequestsMessage covers every category with its own state", () => {
  const msg = openRequestsMessage(
    { found: true, requests: [
      { what_for: "sink leaking", category: "maintenance", spoken: "No one has picked it up yet.", times_asked: 1 },
      { what_for: "help to bathroom", category: "nursing", spoken: "Nora has taken it on.", times_asked: 2 },
    ] },
    { found: true, status: "pending", purpose: "pharmacy", requested_for_date: "2026-10-12", booked: false },
  );
  expect(msg).toMatch(/3 open requests/);
  expect(msg).toMatch(/sink leaking \(maintenance\): No one has picked it up yet/);
  expect(msg).toMatch(/\(nursing\): Nora has taken it on.*Asked 2 times/);
  expect(msg).toMatch(/your ride \(transportation\): still waiting/);
});

test("openRequestsMessage ignores a closed ride and says so when nothing is open", () => {
  expect(openRequestsMessage({ found: false }, { found: true, status: "completed" })).toMatch(/no open request/);
});

test("check_request_status with no category reads every open request", async () => {
  const urls = [];
  global.fetch = jest.fn(async (url) => {
    urls.push(url);
    if (url.includes("/resident-request/open")) return json({ found: true, requests: [{ what_for: "lamp", category: "maintenance", spoken: "Staff have seen it." }] });
    return json({ found: false });
  });
  const out = await executeOperationsTool({ name: "check_request_status", args: {}, ctx: { residentId: "r1" } });
  expect(urls.some((u) => u.includes("/resident-request/open") && u.includes("exclude_category=transportation"))).toBe(true);
  expect(out.message).toMatch(/1 open request.*lamp \(maintenance\)/);
});

test("check_request_status with a category keeps the single-category path", async () => {
  const urls = [];
  global.fetch = jest.fn(async (url) => { urls.push(url); return json({ found: false }); });
  await executeOperationsTool({ name: "check_request_status", args: { category: "nursing" }, ctx: { residentId: "r1" } });
  expect(urls[0]).toMatch(/resident-request\/status\?.*category=nursing/);
});
