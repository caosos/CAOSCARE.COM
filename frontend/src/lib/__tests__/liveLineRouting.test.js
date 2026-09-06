/**
 * Live staff line routing coverage (docs/PROJECT_STATE.md, Level 1
 * directive, 2026-09-06) - acceptance tests 11-13: "get me a nurse" +
 * immediate-help response rings; "get me a nurse" + "just lonely" does
 * not; the routing question's own silence defaults to ringing (tested at
 * the useRealtimeVoice.js/realtimeMessageHandler.js wiring level, not
 * here - this file covers the phrase-grounding decision itself, the same
 * structural-grounding technique already proven for RESTING_PHRASES/
 * ENDING_PHRASES in toggleLightControl.test.js's sibling suite).
 */
process.env.REACT_APP_BACKEND_URL = "http://127.0.0.1:8000";
import { executeCareTool } from "../realtimeCareControl";

function ctx(lastUserText, overrides = {}) {
  return { alert_id: "alert_test", room: "214", last_user_text: lastUserText, ...overrides };
}

function mockFetch() {
  global.fetch = jest.fn(async () => ({ ok: true, json: async () => ({ ok: true }) }));
}

function ringCalls() {
  return global.fetch.mock.calls.filter(([url]) => String(url).includes("/live-line/ring"));
}
function ariaEventCalls() {
  return global.fetch.mock.calls.filter(([url]) => String(url).includes("/aria-event"));
}

beforeEach(() => {
  mockFetch();
});

test("returns undefined for tool names it doesn't own", async () => {
  const r = await executeCareTool({ name: "toggle_light", args: {}, ctx: ctx("turn on the light") });
  expect(r).toBeUndefined();
});

test("no alert_id: graceful message, no network call", async () => {
  const r = await executeCareTool({ name: "request_live_staff", args: {}, ctx: ctx("get me a nurse now", { alert_id: undefined }) });
  expect(r.ok).toBe(false);
  expect(global.fetch).not.toHaveBeenCalled();
});

test.each([
  "I need someone now",
  "I fell",
  "I'm hurt",
  "I can't breathe",
  "please hurry, help me",
])("immediate phrase '%s' rings the live line right away", async (text) => {
  const r = await executeCareTool({ name: "request_live_staff", args: {}, ctx: ctx(text) });
  expect(r.ok).toBe(true);
  expect(r.rang).toBe(true);
  expect(ringCalls()).toHaveLength(1);
});

test.each([
  "just lonely",
  "I wanted some company",
  "no rush, it can wait",
  "not urgent, just wanted to talk",
])("companionable phrase '%s' does NOT ring", async (text) => {
  const r = await executeCareTool({ name: "request_live_staff", args: {}, ctx: ctx(text) });
  expect(r.ok).toBe(true);
  expect(r.rang).toBe(false);
  expect(ringCalls()).toHaveLength(0);
  expect(ariaEventCalls()).toHaveLength(1);
});

test("ambiguous 'get me a nurse' asks the routing question once, without ringing yet", async () => {
  const r = await executeCareTool({ name: "request_live_staff", args: {}, ctx: ctx("get me a nurse", { alert_id: "alert_ambiguous_1" }) });
  expect(r.ok).toBe(true);
  expect(r.rang).toBe(false);
  expect(r.awaiting_answer).toBe(true);
  expect(r.message.toLowerCase()).toContain("right now");
  expect(ringCalls()).toHaveLength(0);
});

test("a second unclear turn for the SAME event rings instead of asking again", async () => {
  const id = "alert_ambiguous_2";
  const first = await executeCareTool({ name: "request_live_staff", args: {}, ctx: ctx("get me a nurse", { alert_id: id }) });
  expect(first.awaiting_answer).toBe(true);
  const second = await executeCareTool({ name: "request_live_staff", args: {}, ctx: ctx("um, I don't know", { alert_id: id }) });
  expect(second.rang).toBe(true);
  expect(ringCalls()).toHaveLength(1);
});
