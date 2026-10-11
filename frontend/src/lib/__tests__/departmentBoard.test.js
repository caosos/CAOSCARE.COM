/** DepartmentWorkspaceDialog renders the department board: members, open work grouped by named worker with its dispatch trail, completed history with receipts; actions go to the canonical task routes. */
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import { trailLine, workerSummary } from "../departmentBoard";

const mockApi = { get: jest.fn(), post: jest.fn() };
jest.mock("../api", () => ({ api: mockApi, API: "http://api.test/api" }));
jest.mock("../auth", () => ({ useAuth: () => ({ user: { user_id: "adm1", role: "admin" } }) }));
jest.mock("@/lib/utils", () => ({ cn: (...a) => a.filter(Boolean).join(" ") }), { virtual: true });
jest.mock("sonner", () => ({ toast: { error: jest.fn(), success: jest.fn() } }));
jest.mock("../../pages/RequestHistoryDialog", () => () => null);
jest.mock("../../components/ui/select", () => {
  const R = require("react");
  return { Select: ({ children, onValueChange }) => R.createElement("div", { "data-onchange": !!onValueChange }, children), SelectContent: ({ children }) => R.createElement("div", null, children),
    SelectItem: ({ children, value }) => R.createElement("div", { "data-value": value }, children), SelectTrigger: (p) => R.createElement("div", { "data-testid": p["data-testid"] }, p.children), SelectValue: () => null };
});
jest.mock("../../components/ui/dialog", () => {
  const R = require("react");
  const pass = ({ children, open }) => (open === false ? null : R.createElement("div", null, children));
  return { Dialog: pass, DialogContent: pass, DialogHeader: pass, DialogTitle: pass, DialogFooter: pass };
});
jest.mock("../../components/ui/textarea", () => { const R = require("react"); return { Textarea: (p) => R.createElement("textarea", { value: p.value, onChange: p.onChange, "data-testid": p["data-testid"] }) }; });
jest.mock("../../components/ui/badge", () => { const R = require("react"); return { Badge: (p) => R.createElement("span", { "data-testid": p["data-testid"] }, p.children) }; });
jest.mock("../../components/ui/button", () => { const R = require("react"); return { Button: (p) => R.createElement("button", { onClick: p.onClick, "data-testid": p["data-testid"] }, p.children) }; });

const Dialog = require("../../pages/DepartmentWorkspaceDialog").default;
globalThis.IS_REACT_ACT_ENVIRONMENT = true;
const flush = () => act(async () => { await Promise.resolve(); await Promise.resolve(); });
const now = new Date().toISOString();
const board = {
  department: { slug: "housekeeping", label: "Housekeeping", active: true },
  members: [{ user_id: "hk1", name: "Demo - Hilda Brooks", role: "staff" }, { user_id: "hk2", name: "Demo - Omar Reyes", role: "staff" }],
  by_worker: [
    { user_id: null, name: "Unassigned", work: [{ task_id: "c", what: "Trash can is full", resident_name: "Rosa", room: "3W05", status: "pending", lifecycle: "open", assigned_to: null,
      delivery: { state: "not_sent", reached: false, label: "Department NOT notified: recorded only, no email/SMS provider is set up" }, trail: [{ at: now, field: "created", text: "front desk" }] }] },
    { user_id: "hk1", name: "Demo - Hilda Brooks", role: "staff", work: [] },
    { user_id: "hk2", name: "Demo - Omar Reyes", role: "staff", work: [{ task_id: "b", what: "Floor needs mopping", status: "in_progress", lifecycle: "in_progress", assigned_to: "hk2", assigned_name: "Demo - Omar Reyes", acknowledged_at: now,
      trail: [{ at: now, field: "created", text: "front desk" }, { at: now, field: "assigned_to", to: "hk2", to_name: "Demo - Omar Reyes", by_name: "Demo - Omar Reyes" }, { at: now, field: "status", to: "in_progress", by_name: "Demo - Omar Reyes" }] }] },
  ],
  history: [{ task_id: "a", what: "Change the bed linens", status: "completed", completed_by_name: "Demo - Hilda Brooks", completed_at: now, duration_minutes: 12, notes: "fresh linens on", receipts_count: 6, trail: [] }],
  counts: { open: 2, unassigned: 1, in_progress: 1, acknowledged: 1, completed_today: 1, closed_shown: 1 },
  can_assign: true,
};
let root, el;
beforeEach(() => { el = document.createElement("div"); document.body.appendChild(el); root = createRoot(el); mockApi.get.mockReset(); mockApi.post.mockReset(); });
afterEach(async () => { await act(async () => root.unmount()); el.remove(); });
const q = (id) => el.querySelector(`[data-testid="${id}"]`);
const render = async () => { await act(async () => root.render(<Dialog department={{ slug: "housekeeping", label: "Housekeeping", active: true }} onClose={() => {}} />)); await flush(); };

test("trail and summary wording come from the record", () => {
  expect(trailLine({ field: "assigned_to", to: "hk2", to_name: "Omar", by_name: "Omar" })).toMatch(/^Assigned to Omar by Omar/);
  expect(trailLine({ field: "status", to: "in_progress", by_name: "Omar" })).toMatch(/^Started by Omar/);
  expect(trailLine({ field: "created", text: "front desk" })).toMatch(/^Created \(front desk\)/);
  expect(workerSummary({ work: [] })).toBe("nothing open");
  expect(workerSummary({ work: [{ status: "in_progress" }, { status: "pending" }] })).toBe("2 open · 1 in progress");
});

test("members, work by named worker with trail, counts and completed history render from one board read", async () => {
  mockApi.get.mockResolvedValue({ data: board });
  await render();
  expect(mockApi.get).toHaveBeenCalledWith("/departments/housekeeping/board");
  expect(q("dept-member-hk1").textContent).toContain("Demo - Hilda Brooks");
  expect(q("dept-worker-summary-unassigned").textContent).toBe("1 open");
  expect(q("dept-worker-summary-hk1").textContent).toBe("nothing open");
  expect(q("dept-worker-summary-hk2").textContent).toBe("1 open · 1 in progress");
  expect(q("dept-trail-b").textContent).toContain("Assigned to Demo - Omar Reyes by Demo - Omar Reyes");
  expect(q("dept-trail-b").textContent).toContain("Started by Demo - Omar Reyes");
  expect(q("dept-status-b").textContent).toBe("in progress");
  expect(q("dept-workspace-counts").textContent).toContain("1 unassigned");
  expect(q("dept-done-a").textContent).toContain("Completed by Demo - Hilda Brooks");
  expect(q("dept-done-a").textContent).toContain("12 min · 6 receipts");
  expect(q("dept-done-a").textContent).toContain("Note: fresh linens on");
});

test("Claim and Start go to the canonical task routes and the board is re-read", async () => {
  mockApi.get.mockResolvedValue({ data: board }); mockApi.post.mockResolvedValue({ data: {} });
  await render();
  await act(async () => { q("dept-claim-c").click(); }); await flush();
  expect(mockApi.post).toHaveBeenCalledWith("/tasks/c/assign", { assigned_to: "adm1" });
  await act(async () => { q("dept-start-c").click(); }); await flush();
  expect(mockApi.post).toHaveBeenCalledWith("/tasks/c/start", undefined);
  expect(mockApi.get).toHaveBeenCalledTimes(3);
});

test("a forbidden board shows the reason, not an empty department", async () => {
  mockApi.get.mockRejectedValue({ response: { status: 403 } });
  await render();
  expect(q("dept-board-error").textContent).toMatch(/only if you belong to it or are an administrator/);
  expect(q("dept-work")).toBeNull();
});

test("a request nobody was told about says so on its card; a reached one shows nothing extra", async () => {
  const withSent = JSON.parse(JSON.stringify(board));
  withSent.by_worker[2].work[0].delivery = { state: "sent", reached: true, label: "sent" };
  mockApi.get.mockResolvedValue({ data: withSent });
  await render();
  expect(q("dept-delivery-c").textContent).toMatch(/^Department NOT notified/);
  expect(q("dept-delivery-b")).toBeNull();
});
