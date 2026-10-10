/** EmailInboundPanel truth: an unreadable endpoint is never presented as "no approved senders" / "no inbound email".
 * Real component mounted with a controllable api; each endpoint fails independently. */
import React, { act } from "react";
import { createRoot } from "react-dom/client";

const mockApi = { get: jest.fn(), post: jest.fn(), delete: jest.fn() };
jest.mock("../api", () => ({ api: mockApi }));
jest.mock("@/lib/utils", () => ({ cn: (...a) => a.filter(Boolean).join(" ") }), { virtual: true });
jest.mock("sonner", () => ({ toast: { error: jest.fn(), success: jest.fn() } }));
jest.mock("../../components/ui/select", () => ({ Select: () => null, SelectContent: () => null, SelectItem: () => null, SelectTrigger: () => null, SelectValue: () => null }));
const Panel = require("../../pages/EmailInboundPanel").default;
globalThis.IS_REACT_ACT_ENVIRONMENT = true;

let root, el;
let allow, msgs;   // each: () => Promise
beforeEach(() => {
  el = document.createElement("div"); document.body.appendChild(el); root = createRoot(el);
  mockApi.get.mockImplementation((u) => (u.startsWith("/email/allowlist") ? allow() : msgs()));
});
afterEach(async () => { await act(async () => root.unmount()); el.remove(); jest.resetAllMocks(); });
const flush = () => act(async () => { for (let i = 0; i < 15; i++) await Promise.resolve(); });
const q = (id) => el.querySelector(`[data-testid=${id}]`);
const ok = (data) => () => Promise.resolve({ data });
const bad = (code = 500) => () => Promise.reject(Object.assign(new Error("x"), { response: { status: code } }));
const mount = async () => { await act(async () => root.render(<Panel />)); await flush(); };
const ENTRY = { entry_id: "e1", lane: "menu", pattern: "chef@x.test", active: true };
const MSG = (status, id = "m1") => ({ inbound_id: id, from_address: "a@x.test", to_addresses: ["menu@in.test"], status, subject: "S", created_at: "2026-10-10T12:00:00Z" });

test("loading: neither empty claim is shown while the reads are pending", async () => {
  allow = () => new Promise(() => {}); msgs = () => new Promise(() => {});
  await mount();
  expect(q("allowlist-loading")).not.toBeNull(); expect(q("inbound-loading")).not.toBeNull();
  expect(el.textContent).not.toContain("all email quarantined"); expect(el.textContent).not.toContain("No inbound email has been received");
});

test("allowlist fails alone (403): no 'quarantined' claim; messages still shown", async () => {
  allow = bad(403); msgs = ok([MSG("routed")]);
  await mount();
  expect(q("allowlist-error")).not.toBeNull(); expect(q("allowlist-retry")).not.toBeNull();
  expect(el.textContent).not.toContain("all email quarantined");
  expect(q("inbound-log")).not.toBeNull(); expect(el.textContent).toContain("Routed");
});

test("messages fail alone: no 'No inbound email has been received'; allowlist still shown", async () => {
  allow = ok([ENTRY]); msgs = bad(500);
  await mount();
  expect(q("inbound-error")).not.toBeNull(); expect(el.textContent).not.toContain("No inbound email has been received");
  expect(el.textContent).toContain("chef@x.test");
});

test("both fail: two errors, no empty claims", async () => {
  allow = bad(); msgs = bad();
  await mount();
  expect(q("allowlist-error")).not.toBeNull(); expect(q("inbound-error")).not.toBeNull();
  expect(el.textContent).not.toContain("all email quarantined"); expect(el.textContent).not.toContain("has been received");
});

test("genuinely empty success: the empty statements ARE shown", async () => {
  allow = ok([]); msgs = ok([]);
  await mount();
  expect(q("allowlist-empty-menu").textContent).toContain("No approved senders"); expect(q("allowlist-empty-activities")).not.toBeNull();
  expect(q("inbound-empty").textContent).toContain("No inbound email has been received");
  expect(q("allowlist-error")).toBeNull(); expect(q("inbound-error")).toBeNull();
});

test("retry recovers after failure", async () => {
  allow = bad(); msgs = bad();
  await mount();
  allow = ok([ENTRY]); msgs = ok([MSG("reconciliation_required")]);
  await act(async () => q("allowlist-retry").click()); await flush();
  expect(q("allowlist-error")).toBeNull(); expect(q("inbound-error")).toBeNull();
  expect(el.textContent).toContain("chef@x.test"); expect(el.textContent).toContain("Needs a person");
});

test("previously loaded data then a failed refresh: kept but marked stale, empty claims say 'as of the last load'", async () => {
  allow = ok([]); msgs = ok([MSG("routed")]);
  await mount();
  // the panel reloads after an approve; that refresh now fails
  allow = bad(); msgs = bad(); mockApi.post.mockResolvedValue({});
  const input = q("allowlist-pattern");
  await act(async () => { Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value").set.call(input, "z@x.test"); input.dispatchEvent(new Event("input", { bubbles: true })); });
  await act(async () => { q("allowlist-form").dispatchEvent(new Event("submit", { bubbles: true, cancelable: true })); }); await flush();
  expect(q("allowlist-stale")).not.toBeNull(); expect(q("inbound-stale")).not.toBeNull();
  expect(q("allowlist-error")).toBeNull();
  expect(el.textContent).toContain("Routed");   // last good data still visible, but flagged
  expect(q("allowlist-empty-menu").textContent).toContain("as of the last successful load");
  expect(q("allowlist-stale").textContent).toContain("may be out of date");
});

test("disable-sender failure is reported, not silently dropped", async () => {
  allow = ok([ENTRY]); msgs = ok([]);
  mockApi.delete.mockRejectedValue(Object.assign(new Error("x"), { response: { data: { detail: "nope" } } }));
  await mount();
  const { toast } = require("sonner");
  await act(async () => el.querySelector("[aria-label='Disable sender']").click()); await flush();
  expect(toast.error).toHaveBeenCalledWith("nope");
});
