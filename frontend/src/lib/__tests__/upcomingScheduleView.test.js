/** UpcomingSchedule (staff) renders the backend's ordered rows grouped by day, with details, lifecycle and ride truth; errors are shown, never a blank "nothing planned". */
import React, { act } from "react";
import { createRoot } from "react-dom/client";

const mockApi = { get: jest.fn() };
jest.mock("../api", () => ({ api: mockApi, API: "http://api.test/api" }));
jest.mock("@/lib/utils", () => ({ cn: (...a) => a.filter(Boolean).join(" ") }), { virtual: true });
jest.mock("../../components/ui/badge", () => { const R = require("react"); return { Badge: (p) => R.createElement("span", { "data-testid": p["data-testid"] }, p.children) }; });

const Upcoming = require("../../components/UpcomingSchedule").default;
globalThis.IS_REACT_ACT_ENVIRONMENT = true;
const flush = () => act(async () => { await Promise.resolve(); await Promise.resolve(); });
const payload = { today: "2026-10-11", days: 14, department: "therapy", items: [
  { task_id: "c", resident_name: "Rosa", room: "3W05", title: "Speech session", requested_for_date: "2026-10-12", requested_for_time_label: "around 3 pm", lifecycle: "open", discipline: "speech therapy" },
  { task_id: "a", resident_name: "Rosa", room: "3W05", title: "PT (knee)", requested_for_date: "2026-10-13", requested_for_time_label: "2:00 PM", lifecycle: "acknowledged", assigned_name: "Tess Ortiz PT",
    provider_name: "Tess Ortiz PT", discipline: "physical therapy", location: "Therapy room",
    ride: { task_id: "r", status: "pending", booked: false, requested_for_date: "2026-10-13", requested_for_time_label: "2:00 PM", run: null } },
] };
let root, el;
beforeEach(() => { el = document.createElement("div"); document.body.appendChild(el); root = createRoot(el); mockApi.get.mockReset(); });
afterEach(async () => { await act(async () => root.unmount()); el.remove(); });
const q = (id) => el.querySelector(`[data-testid="${id}"]`);
const render = async () => { await act(async () => root.render(<Upcoming department="therapy" />)); await flush(); };

test("rows appear grouped by day in the backend's order with details, lifecycle and the ride line", async () => {
  mockApi.get.mockResolvedValue({ data: payload });
  await render();
  expect(mockApi.get).toHaveBeenCalledWith("/tasks/upcoming", { params: { department: "therapy", days: 14 } });
  const days = [...el.querySelectorAll('[data-testid^="upcoming-day-"]')].map((n) => n.getAttribute("data-testid"));
  expect(days).toEqual(["upcoming-day-2026-10-12", "upcoming-day-2026-10-13"]);
  expect(q("upcoming-time-c").textContent).toBe("around 3 pm");
  expect(q("upcoming-details-c").textContent).toBe("Kind: speech therapy");
  expect(q("upcoming-status-a").textContent).toBe("Taken on");
  expect(q("upcoming-details-a").textContent).toBe("With: Tess Ortiz PT (physical therapy) · Where: Therapy room");
  expect(q("upcoming-ride-a").textContent).toBe("Ride: requested for 2:00 PM · 2026-10-13, not yet booked");
  expect(q("upcoming-ride-c")).toBeNull();
});

test("an empty window says so; a failed read shows an error, not an empty schedule", async () => {
  mockApi.get.mockResolvedValue({ data: { ...payload, items: [] } });
  await render();
  expect(q("upcoming-empty")).not.toBeNull();
  await act(async () => root.unmount()); el.remove();
  el = document.createElement("div"); document.body.appendChild(el); root = createRoot(el);
  mockApi.get.mockRejectedValue(new Error("boom"));
  await render();
  expect(q("upcoming-error")).not.toBeNull();
  expect(q("upcoming-empty")).toBeNull();
});

test("overlaps and unchecked times are shown truthfully on the rows", async () => {
  const withConflicts = { ...payload, items: [
    { ...payload.items[0], conflicts: [], conflict_check: "the planned time can't be read as a clock time, so overlap was not checked" },
    { ...payload.items[1], conflicts: [{ task_id: "n1", what: "Wound check", category: "nursing", requested_for_time_label: "2:15 PM" }], conflict_check: null },
  ] };
  mockApi.get.mockResolvedValue({ data: withConflicts });
  await render();
  expect(q("upcoming-conflict-c").textContent).toMatch(/^Overlap not checked: /);
  expect(q("upcoming-conflict-a").textContent).toBe("Overlaps Wound check (nursing) at 2:15 PM.");
});
