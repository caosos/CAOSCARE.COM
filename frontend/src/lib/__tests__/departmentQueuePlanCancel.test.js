/** DepartmentQueue: the planned visit window is shown on the card; Plan saves the two canonical fields; Cancel needs a reason and posts the canonical skip. */
import React, { act } from "react";
import { createRoot } from "react-dom/client";

const mockApi = { get: jest.fn(), post: jest.fn(), patch: jest.fn() };
jest.mock("../api", () => ({ api: mockApi, API: "http://api.test/api" }));
jest.mock("../auth", () => ({ useAuth: () => ({ user: { user_id: "pt1", role: "staff", department: "therapy" } }) }));
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
jest.mock("../../components/ui/input", () => {
  const R = require("react");
  return { Input: (p) => R.createElement("input", { type: p.type || "text", value: p.value, onChange: p.onChange, "data-testid": p["data-testid"] }) };
});
jest.mock("../../components/ui/label", () => { const R = require("react"); return { Label: (p) => R.createElement("label", null, p.children) }; });

const Queue = require("../../pages/DepartmentQueue").default;
globalThis.IS_REACT_ACT_ENVIRONMENT = true;
const flush = () => act(async () => { await Promise.resolve(); await Promise.resolve(); });
const appt = { task_id: "a1", title: "Physical therapy session (knee)", status: "pending", assigned_to: null, visibility_role: "therapy",
  created_at: "2026-10-11T07:00:00Z", requested_for_date: "2026-10-14", requested_for_time_label: "10:00 AM" };
let root, el;
beforeEach(() => {
  el = document.createElement("div"); document.body.appendChild(el); root = createRoot(el);
  mockApi.get.mockReset(); mockApi.post.mockReset(); mockApi.patch.mockReset();
  mockApi.get.mockImplementation((u) => Promise.resolve({ data: u === "/tasks" ? [appt] : [] }));
});
afterEach(async () => { await act(async () => root.unmount()); el.remove(); });
const q = (id) => el.querySelector(`[data-testid=${id}]`);
const setVal = async (node, v, proto) => act(async () => {
  const s = Object.getOwnPropertyDescriptor(proto, "value").set; s.call(node, v); node.dispatchEvent(new Event("input", { bubbles: true }));
});
const render = async () => { await act(async () => root.render(<Queue department="therapy" title="Therapy requests" />)); await flush(); };

test("the planned window is shown on the card", async () => {
  await render();
  expect(q("wo-planned-a1").textContent).toBe("Planned: 10:00 AM · 2026-10-14");
});

test("Plan saves the two canonical window fields with PATCH /tasks/{id}", async () => {
  await render();
  await act(async () => { q("wo-plan-a1").click(); });
  expect(q("wo-plan-date").value).toBe("2026-10-14");
  await setVal(q("wo-plan-date"), "2026-10-15", HTMLInputElement.prototype);
  await setVal(q("wo-plan-label"), "2:00 PM", HTMLInputElement.prototype);
  mockApi.patch.mockResolvedValueOnce({ data: {} });
  await act(async () => { q("wo-plan-save").click(); }); await flush();
  expect(mockApi.patch).toHaveBeenCalledWith("/tasks/a1", { requested_for_date: "2026-10-15", requested_for_time_label: "2:00 PM" });
  expect(q("wo-plan-date")).toBeNull();
});

test("Cancel needs a reason and posts the canonical skip with it", async () => {
  await render();
  await act(async () => { q("wo-cancel-a1").click(); });
  expect(q("wo-cancel-submit").disabled).toBe(true);
  await setVal(q("wo-cancel-reason"), "Therapist out sick; family will rebook", HTMLTextAreaElement.prototype);
  mockApi.post.mockResolvedValueOnce({ data: {} });
  await act(async () => { q("wo-cancel-submit").click(); }); await flush();
  expect(mockApi.post).toHaveBeenCalledWith("/tasks/a1/skip", { notes: "Therapist out sick; family will rebook" });
  expect(q("wo-cancel-reason")).toBeNull();
});
