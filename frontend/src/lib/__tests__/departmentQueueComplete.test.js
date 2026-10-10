/** DepartmentQueue completion: a failed completion keeps the dialog and the typed note; success closes; double click sends once. */
import React, { act } from "react";
import { createRoot } from "react-dom/client";

const mockApi = { get: jest.fn(), post: jest.fn(), patch: jest.fn() };
jest.mock("../api", () => ({ api: mockApi, API: "http://api.test/api" }));
jest.mock("../auth", () => ({ useAuth: () => ({ user: { user_id: "u1", role: "admin", department: "nursing" } }) }));
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
let root, el;
beforeEach(() => {
  el = document.createElement("div"); document.body.appendChild(el); root = createRoot(el);
  mockApi.get.mockReset(); mockApi.post.mockReset();
  mockApi.get.mockImplementation((u) => Promise.resolve({ data: u === "/tasks" ? [{ task_id: "t1", title: "Clean", status: "in_progress", assigned_to: "u1", visibility_role: "nursing", created_at: "2031-01-01T00:00:00Z", priority: "normal" }] : [] }));
});
afterEach(async () => { await act(async () => root.unmount()); el.remove(); });
const q = (id) => el.querySelector(`[data-testid=${id}]`);
const open = async () => {
  await act(async () => root.render(<Queue department="nursing" title="Nursing" />)); await flush();
  await act(async () => { q("wo-complete-t1").click(); });
  const ta = q("wo-complete-notes");
  await act(async () => { const s = Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, "value").set; s.call(ta, "did the thing"); ta.dispatchEvent(new Event("input", { bubbles: true })); });
};

test("failed completion keeps the dialog and the note; a retry that succeeds closes it", async () => {
  await open();
  mockApi.post.mockRejectedValueOnce({ response: { data: { detail: "boom" } } });
  await act(async () => { q("wo-complete-submit").click(); }); await flush();
  expect(q("wo-complete-notes")).not.toBeNull();
  expect(q("wo-complete-notes").value).toBe("did the thing");
  mockApi.post.mockResolvedValueOnce({ data: {} });
  await act(async () => { q("wo-complete-submit").click(); }); await flush();
  expect(q("wo-complete-notes")).toBeNull();
  expect(mockApi.post.mock.calls.filter((c) => c[0].endsWith("/complete")).length).toBe(2);
});

test("double click sends one completion", async () => {
  await open();
  let release; mockApi.post.mockReturnValue(new Promise((r) => { release = r; }));
  await act(async () => { q("wo-complete-submit").click(); q("wo-complete-submit").click(); });
  expect(mockApi.post.mock.calls.filter((c) => c[0].endsWith("/complete")).length).toBe(1);
  await act(async () => { release({ data: {} }); }); await flush();
});
