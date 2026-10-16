/** DepartmentQueue reopen: a completed request shows Reopen for someone who acts for the department; the reason is required and sent. */
import React, { act } from "react";
import { createRoot } from "react-dom/client";

const mockApi = { get: jest.fn(), post: jest.fn(), patch: jest.fn() };
let mockUser = { user_id: "fd1", role: "front_desk", department: null };
jest.mock("../api", () => ({ api: mockApi, API: "http://api.test/api" }));
jest.mock("../auth", () => ({ useAuth: () => ({ user: mockUser }) }));
jest.mock("@/lib/utils", () => ({ cn: (...a) => a.filter(Boolean).join(" ") }), { virtual: true });
jest.mock("sonner", () => ({ toast: { error: jest.fn(), success: jest.fn() } }));
jest.mock("../../pages/MaintenanceWorkOrderForm", () => () => null);
jest.mock("../../pages/RequestHistoryDialog", () => () => null);
jest.mock("../../components/ui/select", () => ({ Select: () => null, SelectContent: () => null, SelectItem: () => null, SelectTrigger: () => null, SelectValue: () => null }));
jest.mock("../../components/ui/dialog", () => {
  const R = require("react");
  const pass = ({ children, open }) => (open === false ? null : R.createElement("div", null, children));
  return { Dialog: pass, DialogContent: pass, DialogHeader: pass, DialogTitle: pass, DialogFooter: pass };
});
jest.mock("../../components/ui/textarea", () => {
  const R = require("react");
  return { Textarea: (p) => R.createElement("textarea", { value: p.value, onChange: p.onChange, "data-testid": p["data-testid"] }) };
});

const Queue = require("../../pages/DepartmentQueue").default;
globalThis.IS_REACT_ACT_ENVIRONMENT = true;
const flush = () => act(async () => { await Promise.resolve(); await Promise.resolve(); });
// Rows are compact; their actions show when a row is expanded (CO-008).
const expandAll = (root0) => act(async () => { (root0 || document).querySelectorAll("[data-testid^=wo-row-]").forEach((b) => { if (b.getAttribute("aria-expanded") !== "true") b.click(); }); });
const done = { task_id: "t9", title: "Callback about parking", status: "completed", assigned_to: "fd1", visibility_role: "administration",
  created_at: "2026-10-11T07:00:00Z", completed_at: "2026-10-11T07:20:00Z", completed_by_name: "Dana" };
let root, el;
beforeEach(() => {
  el = document.createElement("div"); document.body.appendChild(el); root = createRoot(el);
  mockApi.get.mockReset(); mockApi.post.mockReset();
  mockApi.get.mockImplementation((u) => Promise.resolve({ data: u === "/tasks" ? [done] : [] }));
});
afterEach(async () => { await act(async () => root.unmount()); el.remove(); });
const q = (id) => el.querySelector(`[data-testid=${id}]`);
const type = async (ta, v) => act(async () => {
  const s = Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, "value").set; s.call(ta, v); ta.dispatchEvent(new Event("input", { bubbles: true }));
});
const render = async () => {
  await act(async () => root.render(<Queue department="administration" title="Front desk requests" adminMode />)); await flush(); await expandAll();
  await act(async () => { el.querySelector("[data-testid=wo-completed] summary")?.click(); });
};

test("front desk sees Reopen on a completed Administration request; empty reason is disabled; reason is sent", async () => {
  await render();
  expect(q("wo-reopen-t9")).not.toBeNull();
  await act(async () => { q("wo-reopen-t9").click(); });
  expect(q("wo-reopen-submit").disabled).toBe(true);
  expect(document.body.textContent).toMatch(/resident sees this text on their screen and Aria may read it/);
  await type(q("wo-reopen-reason"), "Resident called back: the pass was never issued.");
  expect(q("wo-reopen-submit").disabled).toBe(false);
  mockApi.post.mockResolvedValueOnce({ data: {} });
  await act(async () => { q("wo-reopen-submit").click(); }); await flush();
  const calls = mockApi.post.mock.calls.filter((c) => c[0] === "/tasks/t9/reopen");
  expect(calls.length).toBe(1);
  expect(calls[0][1]).toEqual({ reason: "Resident called back: the pass was never issued." });
  expect(q("wo-reopen-reason")).toBeNull();
});

test("a failed reopen keeps the dialog and the typed reason", async () => {
  await render();
  await act(async () => { q("wo-reopen-t9").click(); });
  await type(q("wo-reopen-reason"), "still broken");
  mockApi.post.mockRejectedValueOnce({ response: { data: { detail: "nope" } } });
  await act(async () => { q("wo-reopen-submit").click(); }); await flush();
  expect(q("wo-reopen-reason")).not.toBeNull();
  expect(q("wo-reopen-reason").value).toBe("still broken");
});

test("nursing staff in another department see no Reopen on an Administration request", async () => {
  mockUser = { user_id: "n1", role: "staff", department: "nursing" };
  await render();
  expect(q("wo-reopen-t9")).toBeNull();
  mockUser = { user_id: "fd1", role: "front_desk", department: null };
});
