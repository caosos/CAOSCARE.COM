/** RequestDetailDialog (admin/front desk): shows the appointment details and saves them through the same PATCH as the queue's Plan dialog. */
import React, { act } from "react";
import { createRoot } from "react-dom/client";

const mockApi = { get: jest.fn(), post: jest.fn(), patch: jest.fn() };
jest.mock("../api", () => ({ api: mockApi, API: "http://api.test/api" }));
jest.mock("@/lib/utils", () => ({ cn: (...a) => a.filter(Boolean).join(" ") }), { virtual: true });
jest.mock("sonner", () => ({ toast: { error: jest.fn(), success: jest.fn() } }));
let mockUser = { user_id: "adm1", role: "admin" };
jest.mock("../auth", () => ({ useAuth: () => ({ user: mockUser }) }));
jest.mock("../../components/RequestTimeline", () => () => null);
jest.mock("../../components/ui/dialog", () => {
  const R = require("react");
  const pass = ({ children, open }) => (open === false ? null : R.createElement("div", null, children));
  return { Dialog: pass, DialogContent: pass, DialogHeader: pass, DialogTitle: pass };
});
jest.mock("../../components/ui/badge", () => { const R = require("react"); return { Badge: (p) => R.createElement("span", null, p.children) }; });
jest.mock("../../components/ui/button", () => { const R = require("react"); return { Button: (p) => R.createElement("button", { onClick: p.onClick, disabled: p.disabled, "data-testid": p["data-testid"] }, p.children) }; });
jest.mock("../../components/ui/textarea", () => {
  const R = require("react");
  return { Textarea: (p) => R.createElement("textarea", { value: p.value, onChange: p.onChange, "data-testid": p["data-testid"] }) };
});
jest.mock("../../components/ui/input", () => {
  const R = require("react");
  return { Input: (p) => R.createElement("input", { type: p.type || "text", value: p.value, onChange: p.onChange, "data-testid": p["data-testid"] }) };
});

const Dialog = require("../../pages/RequestDetailDialog").default;
globalThis.IS_REACT_ACT_ENVIRONMENT = true;
const flush = () => act(async () => { await Promise.resolve(); await Promise.resolve(); });
const task = { task_id: "a1", title: "Physical therapy session (knee)", status: "pending", category: "therapy", source: "front_desk", priority: "normal",
  created_at: "2026-10-11T07:00:00Z", requested_for_date: "2026-10-14", requested_for_time_label: "10:00 AM",
  provider_name: "Tess Ortiz PT", discipline: "physical therapy", location: "Therapy room, 2nd floor", notes: "" };
let root, el;
beforeEach(() => {
  el = document.createElement("div"); document.body.appendChild(el); root = createRoot(el);
  mockApi.get.mockReset(); mockApi.patch.mockReset();
  mockApi.get.mockImplementation((u) => Promise.resolve({ data: u === "/tasks/a1/detail" ? { task, receipts: [] } : [] }));
});
afterEach(async () => { await act(async () => root.unmount()); el.remove(); });
const q = (id) => el.querySelector(`[data-testid=${id}]`);
const setVal = async (node, v) => act(async () => {
  const s = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value").set; s.call(node, v); node.dispatchEvent(new Event("input", { bubbles: true }));
});
beforeEach(() => { mockUser = { user_id: "adm1", role: "admin" }; });
const render = async () => { await act(async () => root.render(<Dialog taskId="a1" open onOpenChange={() => {}} />)); await flush(); };

test("the stored details are shown and pre-fill the form", async () => {
  await render();
  expect(q("request-details-line").textContent).toBe("With: Tess Ortiz PT (physical therapy) · Where: Therapy room, 2nd floor");
  expect(q("request-provider").value).toBe("Tess Ortiz PT");
  expect(q("request-discipline").value).toBe("physical therapy");
  expect(q("request-location").value).toBe("Therapy room, 2nd floor");
});

test("saving sends the window, the three details and the note in one canonical PATCH; a cleared field is sent as empty", async () => {
  await render();
  await setVal(q("request-location"), "Clinic downtown, suite 4");
  await setVal(q("request-discipline"), "");
  mockApi.patch.mockResolvedValueOnce({ data: {} });
  await act(async () => { q("request-save-update-btn").click(); }); await flush();
  expect(mockApi.patch).toHaveBeenCalledWith("/tasks/a1", {
    requested_for_date: "2026-10-14", requested_for_time_label: "10:00 AM",
    provider_name: "Tess Ortiz PT", discipline: "", location: "Clinic downtown, suite 4", notes: "",
  });
});

test("no details line when none are set", async () => {
  mockApi.get.mockImplementation((u) => Promise.resolve({ data: u === "/tasks/a1/detail" ? { task: { ...task, provider_name: null, discipline: null, location: null }, receipts: [] } : [] }));
  await render();
  expect(q("request-details-line")).toBeNull();
  expect(q("request-provider").value).toBe("");
});

test("front desk sees the plan read-only with the rule stated; no form is offered", async () => {
  mockUser = { user_id: "fd1", role: "front_desk" };
  await render();
  expect(q("request-plan-readonly").textContent).toContain("10:00 AM · 2026-10-14");
  expect(q("request-plan-readonly").textContent).toContain("With: Tess Ortiz PT (physical therapy) · Where: Therapy room, 2nd floor");
  expect(q("request-plan-readonly").textContent).toContain("Only therapy staff, the assignee or an administrator");
  expect(q("request-provider")).toBeNull();
  expect(q("request-save-update-btn")).toBeNull();
});

test("therapy staff and the assignee can edit; nursing staff cannot", async () => {
  mockUser = { user_id: "pt1", role: "staff", department: "therapy" };
  await render();
  expect(q("request-provider")).not.toBeNull();
  await act(async () => root.unmount()); el.remove(); el = document.createElement("div"); document.body.appendChild(el); root = createRoot(el);
  mockUser = { user_id: "n1", role: "staff", department: "nursing" };
  await render();
  expect(q("request-provider")).toBeNull();
  expect(q("request-plan-readonly")).not.toBeNull();
});
