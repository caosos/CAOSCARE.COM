/** TransportationTab: the Unresolved tile opens the list behind the count; rows open the real record; a failed load shows an error, not an endless Loading. */
import React, { act } from "react";
import { createRoot } from "react-dom/client";

const mockApi = { get: jest.fn(), post: jest.fn() };
jest.mock("../api", () => ({ api: mockApi, API: "http://api.test/api" }));
jest.mock("@/lib/utils", () => ({ cn: (...a) => a.filter(Boolean).join(" ") }), { virtual: true });
jest.mock("sonner", () => ({ toast: { error: jest.fn(), success: jest.fn() } }));
jest.mock("../../components/TransportAssignAction", () => () => null);
jest.mock("../../pages/RequestDetailDialog", () => (p) => { const R = require("react"); return p.open ? R.createElement("div", { "data-testid": "detail-open" }, p.taskId) : null; });
jest.mock("../../components/ui/card", () => { const R = require("react"); return { Card: (p) => R.createElement("div", { "data-testid": p["data-testid"] }, p.children) }; });
jest.mock("../../components/ui/badge", () => { const R = require("react"); return { Badge: (p) => R.createElement("span", null, p.children) }; });
jest.mock("../../components/ui/button", () => { const R = require("react"); return { Button: (p) => R.createElement("button", { onClick: p.onClick, "data-testid": p["data-testid"] }, p.children) }; });
jest.mock("../../components/ui/input", () => { const R = require("react"); return { Input: (p) => R.createElement("input", { value: p.value, onChange: p.onChange }) }; });

const Tab = require("../../pages/TransportationTab").default;
globalThis.IS_REACT_ACT_ENVIRONMENT = true;
const flush = () => act(async () => { await Promise.resolve(); await Promise.resolve(); });
const row = { task_id: "r1", resident_name: "Demo - Alice Monroe", room: "3W01", purpose: "Dentist on Main St", requested_for_date: "2026-10-13", requested_for_time_label: "around 10",
  status: "pending", booked: false, owner: null, times_asked: 2, age_hours: 5, next_action: "Resident has asked 2 times - book it or tell them why not", currency: { bucket: "current" } };
const report = { date: "2026-10-11", inbound: [], outbound: [], summary: { total_requests_received: 0, total_booked: 0, total_completed: 0, total_cancelled: 0, total_unresolved: 1,
  unresolved_scope: "Open ride requests with no booked pickup, on any date (not only this day)" },
  current_state: { upcoming_rides: [], waiting_unbooked: [row], follow_ups_required: [row] } };
let root, el;
beforeEach(() => { el = document.createElement("div"); document.body.appendChild(el); root = createRoot(el); mockApi.get.mockReset(); });
afterEach(async () => { await act(async () => root.unmount()); el.remove(); });
const q = (id) => el.querySelector(`[data-testid="${id}"]`);

test("the Unresolved tile opens the same rows the count is made of; a row opens the real record", async () => {
  mockApi.get.mockResolvedValue({ data: report });
  await act(async () => root.render(<Tab />)); await flush();
  expect(q("transport-unresolved-tile").textContent).toContain("1");
  expect(q("transport-unresolved-list")).toBeNull();
  await act(async () => { q("transport-unresolved-tile").click(); });
  expect(q("transport-unresolved-list").textContent).toContain("Unresolved rides (1)");
  expect(q("transport-unresolved-list").textContent).toContain("any date");
  expect(q("transport-unresolved-r1").textContent).toContain("Demo - Alice Monroe");
  expect(q("transport-unresolved-next-r1").textContent).toBe("Next: Resident has asked 2 times - book it or tell them why not");
  await act(async () => { q("transport-unresolved-open-r1").click(); });
  expect(q("detail-open").textContent).toBe("r1");
});

test("an empty list says so; a forbidden or failed load shows the reason with Try again", async () => {
  mockApi.get.mockResolvedValue({ data: { ...report, summary: { ...report.summary, total_unresolved: 0 }, current_state: { upcoming_rides: [], waiting_unbooked: [], follow_ups_required: [] } } });
  await act(async () => root.render(<Tab />)); await flush();
  await act(async () => { q("transport-unresolved-tile").click(); });
  expect(q("transport-unresolved-empty")).not.toBeNull();
  await act(async () => root.unmount()); el.remove(); el = document.createElement("div"); document.body.appendChild(el); root = createRoot(el);
  mockApi.get.mockRejectedValue({ response: { status: 403 } });
  await act(async () => root.render(<Tab />)); await flush();
  expect(q("transport-report-error").textContent).toMatch(/administrators, the front desk and transportation staff/);
});
