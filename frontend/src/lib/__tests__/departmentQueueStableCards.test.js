/** DepartmentQueue: a parent re-render must update request cards in place, not rebuild them (a rebuilt card closes an open "Assign to" list before the choice lands). */
import React, { act } from "react";
import { createRoot } from "react-dom/client";

const mockApi = { get: jest.fn(), post: jest.fn(), patch: jest.fn() };
let mockUser = { user_id: "a1", role: "admin", department: null };
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
const open = { task_id: "t1", title: "Help to the bathroom", status: "pending", priority: "high", visibility_role: "nursing",
  created_at: new Date().toISOString() };
let root, el;
beforeEach(() => {
  el = document.createElement("div"); document.body.appendChild(el); root = createRoot(el);
  mockApi.get.mockImplementation((u) => Promise.resolve({ data: u === "/tasks" ? [open] : [] }));
});
afterEach(async () => { await act(async () => root.unmount()); el.remove(); });

test("a re-render keeps the same card element", async () => {
  await act(async () => root.render(<Queue department="nursing" title="Nursing requests" adminMode />)); await flush();
  const card = el.querySelector("[data-testid=wo-t1]");
  expect(card).not.toBeNull();
  await act(async () => root.render(<Queue department="nursing" title="Nursing requests" adminMode />)); await flush();
  expect(el.querySelector("[data-testid=wo-t1]")).toBe(card);
});
