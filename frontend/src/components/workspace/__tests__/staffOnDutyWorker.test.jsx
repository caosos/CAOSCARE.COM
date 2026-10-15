import React, { act } from "react";
import { createRoot } from "react-dom/client";

jest.mock("@/lib/utils", () => ({ cn: (...values) => values.filter(Boolean).join(" ") }), { virtual: true });
jest.mock("sonner", () => ({ toast: { success: jest.fn(), error: jest.fn() } }));
jest.mock("../../../lib/api", () => ({ api: { get: jest.fn(), post: jest.fn() } }));
jest.mock("../../../pages/RequestDetailDialog", () => () => null);

import RecordsDialog from "../RecordsDialog";
import { WIDGET_BY_ID } from "../../../lib/workspaceCatalog";
import { api } from "../../../lib/api";

globalThis.IS_REACT_ACT_ENVIRONMENT = true;

const SERVER = "sim:staff:kitchen:dining_server:03";
const clock = { absolute_minute: 1035, day: 1, hh_mm: "17:15" };
const tray = { task_id: "t-tray", what: "Dinner delivery to the apartment", status: "in_progress", department: "kitchen",
  routine: "dinner_room_service", resident: { id: "sim:resident:002", name: "SIM Resident 002", room: "SIM-002" },
  worker: { id: SERVER, name: "SIM - Dining Server 03", real_staff: false }, requested: clock };
const widget = { name: "staff_on_duty", world: "simulated", total: 2, value: 2, run: { run_id: "run-1" },
  explanation: "Simulated workers on site per the staffing rota.", period: { label: "Day 1" },
  rows: [{ id: SERVER, worker_id: SERVER, name: "SIM - Dining Server 03", simulated: true, detail: "kitchen · dining server · late shift" },
         { id: "sim:staff:transportation:driver:01", worker_id: "sim:staff:transportation:driver:01", name: "SIM - Driver 01", simulated: true, detail: "transportation · driver · early shift" }] };
const worker = { status: "loaded", run_id: "run-1", as_of: clock, simulated: true,
  worker: { actor_id: SERVER, name: "SIM - Dining Server 03", job_role: "dining_server", department: "kitchen",
            department_label: "Dining / Kitchen", actor_type: "simulated-agent", identity_basis: "synthetic" },
  duty: "on_duty", shift_now: "late", state: "working", state_label: "On duty · working a ticket", on_break: null, location: null,
  covered_by: null, week: [{ day: 1, weekday: "Monday", shift: "late", start: "12:00", end: "20:00", duty: "on_site" }],
  current: [tray], today: { day: 1, weekday: "Monday", assigned: [tray], assigned_total: 1, completed_total: 0 },
  role_details: { kind: "meal_service", current_service: "Dinner delivery to the apartment", served_today: { "lunch · dining room": 4 } },
  completed_total: 0, completed: [], schedule: { today: [], tomorrow: [] }, next_planned: [] };

beforeEach(() => {
  api.get.mockReset();
  api.get.mockImplementation((url) => {
    if (url === "/ops/metrics/widgets/staff_on_duty") return Promise.resolve({ data: widget });
    if (url === `/simulator/community/dashboard/workers/${encodeURIComponent(SERVER)}`) return Promise.resolve({ data: worker });
    return Promise.reject(new Error(`unexpected ${url}`));
  });
});

async function open() {
  const container = document.createElement("div");
  document.body.appendChild(container);
  const root = createRoot(container);
  await act(async () => root.render(
    <RecordsDialog widget={WIDGET_BY_ID.staff_on_duty} view={{ world: "simulated" }} open onOpenChange={() => {}} />));
  await act(async () => {});
  return root;
}

test("each worker under Staff On Duty is a keyboard-reachable button", async () => {
  const root = await open();
  const rows = document.querySelectorAll('[data-testid="ws-worker-row"]');
  expect(rows).toHaveLength(2);
  rows.forEach((row) => expect(row.tagName).toBe("BUTTON"));
  act(() => root.unmount());
});

test("clicking a dining server opens that exact worker's detail with meal-service truth", async () => {
  const root = await open();
  const row = [...document.querySelectorAll('[data-testid="ws-worker-row"]')].find((b) => b.textContent.includes("Dining Server 03"));
  await act(async () => { row.focus(); row.click(); });
  await act(async () => {});
  expect(api.get).toHaveBeenCalledWith(`/simulator/community/dashboard/workers/${encodeURIComponent(SERVER)}`);
  const detail = document.querySelector('[data-testid="worker-detail"]');
  expect(detail.textContent).toContain("SIM - Dining Server 03");
  expect(detail.textContent).toContain("SIMULATED");
  expect(detail.textContent).toContain("On duty · working a ticket");
  expect(detail.textContent).toContain("1 assigned today · 0 completed today");
  expect(detail.textContent).toContain("Now: Dinner delivery to the apartment");
  expect(detail.textContent).toContain("Break: not tracked (unknown)");
  act(() => root.unmount());
});
