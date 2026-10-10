/** CommunicationsTab truth: an unreadable provider status or delivery log is never shown as "not configured" /
 * "No notifications". Real component mounted with a controllable api; each GET fails independently. */
import React, { act } from "react";
import { createRoot } from "react-dom/client";

const mockApi = { get: jest.fn(), post: jest.fn() };
jest.mock("../api", () => ({ api: mockApi }));
jest.mock("@/lib/utils", () => ({ cn: (...a) => a.filter(Boolean).join(" ") }), { virtual: true });
jest.mock("sonner", () => ({ toast: { error: jest.fn(), success: jest.fn() } }));
jest.mock("../../components/EmailReadiness", () => ({ __esModule: true, default: () => null }));
jest.mock("../../pages/EmailInboundPanel", () => ({ __esModule: true, default: () => null }));
jest.mock("../../components/ui/select", () => ({
  Select: ({ onValueChange }) => <button data-testid="filter-failed" onClick={() => onValueChange("failed")} />,
  SelectContent: () => null, SelectItem: () => null, SelectTrigger: () => null, SelectValue: () => null,
}));
const Tab = require("../../pages/CommunicationsTab").default;
globalThis.IS_REACT_ACT_ENVIRONMENT = true;

let root, el, status, notifs;   // each: (url) => Promise
beforeEach(() => {
  el = document.createElement("div"); document.body.appendChild(el); root = createRoot(el);
  mockApi.get.mockImplementation((u) => (u.startsWith("/notifications/status") ? status(u) : notifs(u)));
});
afterEach(async () => { await act(async () => root.unmount()); el.remove(); jest.resetAllMocks(); });
const flush = () => act(async () => { for (let i = 0; i < 15; i++) await Promise.resolve(); });
const q = (id) => el.querySelector(`[data-testid=${id}]`);
const ok = (data) => () => Promise.resolve({ data });
const bad = () => () => Promise.reject(Object.assign(new Error("x"), { response: { status: 500 } }));
const mount = async () => { await act(async () => root.render(<Tab />)); await flush(); };
const STATUS = { resend_configured: true, resend_from: "care@x.test", twilio_configured: false };
const N = (id, status = "sent") => ({ notification_id: id, channel: "email", to: `${id}@x.test`, status, body: `body-${id}`, created_at: "2026-10-10T12:00:00Z" });
const pick = async () => { await act(async () => q("filter-failed").click()); await flush(); };

test("loading: no 'not configured' and no 'No notifications' while reads are pending", async () => {
  status = () => new Promise(() => {}); notifs = () => new Promise(() => {});
  await mount();
  expect(q("provider-loading")).not.toBeNull(); expect(q("notif-loading")).not.toBeNull();
  expect(el.textContent).not.toContain("not configured"); expect(el.textContent).not.toContain("No notifications");
});

test("status fails alone: provider says unavailable (not 'not configured'); the log still shows", async () => {
  status = bad(); notifs = ok([N("a")]);
  await mount();
  expect(q("provider-error")).not.toBeNull(); expect(el.textContent).not.toContain("not configured");
  expect(q("provider-badges")).toBeNull();
  expect(el.textContent).toContain("body-a");
});

test("log fails alone: no 'No notifications'; provider status still shown", async () => {
  status = ok(STATUS); notifs = bad();
  await mount();
  expect(q("notif-error")).not.toBeNull(); expect(q("notif-empty")).toBeNull();
  expect(el.textContent).not.toContain("No notifications");
  expect(el.textContent).toContain("Resend email - configured");
});

test("both fail: two errors, no claims", async () => {
  status = bad(); notifs = bad();
  await mount();
  expect(q("provider-error")).not.toBeNull(); expect(q("notif-error")).not.toBeNull();
  expect(el.textContent).not.toContain("not configured"); expect(el.textContent).not.toContain("No notifications");
});

test("genuinely empty success says 'No notifications.'; a real 'not configured' provider is still shown", async () => {
  status = ok(STATUS); notifs = ok([]);
  await mount();
  expect(q("notif-empty").textContent).toBe("No notifications.");
  expect(el.textContent).toContain("Twilio SMS - not configured");
  expect(q("notif-error")).toBeNull(); expect(q("provider-error")).toBeNull();
});

test("retry recovers both reads", async () => {
  status = bad(); notifs = bad();
  await mount();
  status = ok(STATUS); notifs = ok([N("a")]);
  await act(async () => q("notif-retry").click()); await flush();
  expect(q("provider-error")).toBeNull(); expect(q("notif-error")).toBeNull();
  expect(el.textContent).toContain("body-a"); expect(el.textContent).toContain("Resend email - configured");
});

test("status refresh failure keeps the last good provider status, marked stale (log fails for a different filter)", async () => {
  status = ok(STATUS); notifs = ok([N("a")]);
  await mount();
  status = bad(); notifs = bad();
  await pick();   // filter change: both reads fail
  expect(q("notif-error")).not.toBeNull(); expect(el.textContent).not.toContain("body-a");   // 'all' rows are not shown for 'failed'
  expect(q("provider-stale")).not.toBeNull(); expect(q("provider-stale").textContent).toContain("may be out of date");
  expect(el.textContent).toContain("Resend email - configured");
});

test("failed filter change never leaves the previous filter's rows looking current; recovering shows the new filter's rows", async () => {
  status = ok(STATUS); notifs = ok([N("all1")]);
  await mount();
  notifs = bad();
  await pick();
  expect(q("notif-error")).not.toBeNull(); expect(el.textContent).not.toContain("body-all1");
  notifs = ok([N("f1", "failed")]);
  await act(async () => q("notif-retry").click()); await flush();
  expect(el.textContent).toContain("body-f1"); expect(el.textContent).not.toContain("body-all1"); expect(q("notif-error")).toBeNull();
});

test("same-filter failed refresh (retry after success then failure) keeps rows, marked stale, empty says 'as of the last load'", async () => {
  status = ok(STATUS); notifs = ok([]);
  await mount();
  expect(q("notif-empty").textContent).toBe("No notifications.");
  // refresh via the Send test path: submit the form, which calls load() for the same filter
  status = bad(); notifs = bad(); mockApi.post.mockResolvedValue({ data: { status: "logged" } });
  await act(async () => q("send-test-btn").click()); await flush();
  const form = document.body.querySelector("form");
  const input = document.body.querySelector("[data-testid=test-to]");
  await act(async () => { Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value").set.call(input, "a@x.test"); input.dispatchEvent(new Event("input", { bubbles: true })); });
  await act(async () => { form.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true })); }); await flush();
  expect(q("notif-stale")).not.toBeNull(); expect(q("notif-error")).toBeNull();
  expect(q("notif-empty").textContent).toContain("as of the last successful load");
});

test("old/new reply order: a slow reply for an earlier filter cannot overwrite the newer one", async () => {
  let slow;
  status = ok(STATUS);
  notifs = (u) => (u.includes("status=") ? Promise.resolve({ data: [N("new", "failed")] }) : new Promise((r) => { slow = r; }));
  await mount();               // 'all' still pending
  await pick();                // newer filter resolves first
  expect(el.textContent).toContain("body-new");
  await act(async () => { slow({ data: [N("old")] }); }); await flush();
  expect(el.textContent).toContain("body-new"); expect(el.textContent).not.toContain("body-old");
});

// ---- pending-state truth (da-c96b221759) ----
const never = () => new Promise(() => {});
function deferred() { let res, rej; const p = new Promise((a, b) => { res = a; rej = b; }); return { p, res, rej }; }

test("filter change: while the new filter is pending, no old rows and no empty claim are shown; then resolve", async () => {
  status = ok(STATUS); notifs = ok([N("A1")]);
  await mount();
  expect(el.textContent).toContain("body-A1");
  const d = deferred(); notifs = () => d.p;
  await pick();
  expect(el.textContent).not.toContain("body-A1"); expect(el.textContent).not.toContain("No notifications");
  expect(q("notif-loading")).not.toBeNull();
  await act(async () => d.res({ data: [N("B1", "failed")] })); await flush();
  expect(el.textContent).toContain("body-B1"); expect(q("notif-loading")).toBeNull();
});

test("filter change pending then rejects: error (not A rows), then retry recovers", async () => {
  status = ok(STATUS); notifs = ok([N("A1")]);
  await mount();
  const d = deferred(); notifs = () => d.p;
  await pick();
  await act(async () => d.rej(Object.assign(new Error("x"), { response: { status: 500 } }))); await flush();
  expect(q("notif-error")).not.toBeNull(); expect(el.textContent).not.toContain("body-A1");
  notifs = ok([N("B2", "failed")]);
  await act(async () => q("notif-retry").click()); await flush();
  expect(el.textContent).toContain("body-B2"); expect(q("notif-error")).toBeNull();
});

test("status pending forever: the successful log is still shown", async () => {
  status = never; notifs = ok([N("a")]);
  await mount();
  expect(el.textContent).toContain("body-a"); expect(q("provider-loading")).not.toBeNull();
  expect(el.textContent).not.toContain("not configured");
});

test("log pending forever: the successful provider status is still shown", async () => {
  status = ok(STATUS); notifs = never;
  await mount();
  expect(el.textContent).toContain("Resend email - configured"); expect(q("notif-loading")).not.toBeNull();
  expect(el.textContent).not.toContain("No notifications");
});

test("unmounted while pending: late replies do not update (no error, no crash)", async () => {
  const ds = deferred(), dn = deferred(); status = () => ds.p; notifs = () => dn.p;
  await mount();
  await act(async () => root.unmount());
  const spy = jest.spyOn(console, "error").mockImplementation(() => {});
  await act(async () => { ds.res({ data: STATUS }); dn.res({ data: [N("late")] }); }); await flush();
  expect(spy).not.toHaveBeenCalled(); spy.mockRestore();
  root = createRoot(el);   // afterEach unmounts this
});
