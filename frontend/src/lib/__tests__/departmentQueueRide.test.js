/** DepartmentQueue: a planned request shows Ride; the linked ride's line comes from GET /tasks/{id}/ride; Ride posts the create-or-attach action. */
import React, { act } from "react";
import { createRoot } from "react-dom/client";

const mockApi = { get: jest.fn(), post: jest.fn(), patch: jest.fn() };
jest.mock("../api", () => ({ api: mockApi, API: "http://api.test/api" }));
jest.mock("../auth", () => ({ useAuth: () => ({ user: { user_id: "pt1", role: "staff", department: "therapy" } }) }));
jest.mock("@/lib/utils", () => ({ cn: (...a) => a.filter(Boolean).join(" ") }), { virtual: true });
jest.mock("sonner", () => ({ toast: { error: jest.fn(), success: jest.fn() } }));
jest.mock("../../pages/MaintenanceWorkOrderForm", () => () => null);
jest.mock("../../pages/RequestHistoryDialog", () => () => null);
jest.mock("../../pages/QueueDialogs", () => ({ ConflictDialog: () => null, PlanWindowDialog: () => null, ReasonDialog: () => null }));
jest.mock("../../components/ui/select", () => ({ Select: () => null, SelectContent: () => null, SelectItem: () => null, SelectTrigger: () => null, SelectValue: () => null }));
jest.mock("../../components/ui/dialog", () => {
  const R = require("react");
  const pass = ({ children, open }) => (open === false ? null : R.createElement("div", null, children));
  return { Dialog: pass, DialogContent: pass, DialogHeader: pass, DialogTitle: pass, DialogFooter: pass };
});
jest.mock("../../components/ui/textarea", () => { const R = require("react"); return { Textarea: (p) => R.createElement("textarea", p) }; });

const Queue = require("../../pages/DepartmentQueue").default;
globalThis.IS_REACT_ACT_ENVIRONMENT = true;
const flush = () => act(async () => { await Promise.resolve(); await Promise.resolve(); await Promise.resolve(); });
const planned = { task_id: "a1", title: "PT (knee)", status: "pending", resident_id: "r1", visibility_role: "therapy", created_at: "2026-10-11T07:00:00Z", requested_for_date: "2026-10-15", requested_for_time_label: "2:00 PM" };
const withRide = { ...planned, task_id: "a2", linked_ride_task_id: "t9" };
let root, el;
beforeEach(() => {
  el = document.createElement("div"); document.body.appendChild(el); root = createRoot(el);
  mockApi.get.mockReset(); mockApi.post.mockReset();
  mockApi.get.mockImplementation((u) => {
    if (u === "/tasks") return Promise.resolve({ data: [planned, withRide] });
    if (u === "/tasks/a2/ride") return Promise.resolve({ data: { linked: true, ride: { status: "pending", booked: true, run: { depart_time: "13:30", date: "2026-10-15", status: "scheduled", driver_name: "Pete", vehicle_name: "Van" } } } });
    return Promise.resolve({ data: [] });
  });
});
afterEach(async () => { await act(async () => root.unmount()); el.remove(); });
const q = (id) => el.querySelector(`[data-testid=${id}]`);

test("the linked ride's line is shown and the Ride button appears only where no open ride is linked", async () => {
  await act(async () => root.render(<Queue department="therapy" title="Therapy requests" />)); await flush(); await flush();
  expect(q("wo-ride-status-a2").textContent).toBe("Ride: booked 13:30 with Pete, Van (2026-10-15)");
  expect(q("wo-ride-a2")).toBeNull();
  expect(q("wo-ride-a1")).not.toBeNull();
  mockApi.post.mockResolvedValueOnce({ data: { task_id: "t10", already_linked: false, attached_existing: false, booked: false } });
  await act(async () => { q("wo-ride-a1").click(); }); await flush();
  expect(mockApi.post).toHaveBeenCalledWith("/tasks/a1/ride");
});
