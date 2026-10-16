import React, { act } from "react";
import { createRoot } from "react-dom/client";

jest.mock("@/lib/utils", () => ({ cn: (...values) => values.filter(Boolean).join(" ") }), { virtual: true });
jest.mock("sonner", () => ({ toast: { success: jest.fn(), error: jest.fn() } }));
jest.mock("../../../lib/api", () => ({ api: { get: jest.fn(), post: jest.fn() } }));

import LiveDashboard from "../LiveDashboard";
import { api } from "../../../lib/api";

globalThis.IS_REACT_ACT_ENVIRONMENT = true;

const SLUGS = ["nursing", "kitchen", "housekeeping", "maintenance", "transportation", "activities", "front_desk", "administration"];
const clock = { absolute_minute: 600, day: 1, hh_mm: "10:00" };
const ticket = { task_id: "t-wait", what: "Scheduled simulated housekeeping room service.", status: "pending",
  department: "housekeeping", resident: { id: "sim:resident:001", name: "SIM Resident 001", room: "SIM-001" },
  worker: { id: null, name: null, real_staff: false }, requested: clock, waiting_minutes: 75, overdue: true };
const summary = {
  status: "loaded", truth: "Counts are exact.",
  run: { run_id: "run-1", state: "RUNNING", clock, as_of: clock, executor_behind_minutes: 0, progress_percent: 1.2 },
  counts: { workers_on_duty: 18, workers_on_call: 1, residents: 75, pending: 4, in_progress: 3, completed: 900, overdue: 1 },
  departments: SLUGS.map((slug) => ({ slug, label: `Dept ${slug}`, status: "on_duty", hours: "24 hours", on_duty: 2,
    on_call: 0, waiting: 1, in_progress: 1, completed_today: 5, overdue: slug === "housekeeping" ? 1 : 0 })),
  staff: [{ actor_id: "sim:staff:nursing:care_aide:01", name: "SIM - Care Aide 01", department: "nursing", job_role: "care_aide", availability: "busy", duty: "on_duty" }],
  residents: [{ resident_id: "sim:resident:001", name: "SIM Resident 001", room: "SIM-001", open_requests: 1 }],
};
const department = (slug) => ({ status: "loaded", slug, label: `Dept ${slug}`, as_of: clock, day: 1,
  people: [{ actor_id: "sim:staff:x:01", name: "SIM - Worker 01", job_role: "worker", duty: "on_duty", today: [], current: null }],
  schedule_today: [], work: { waiting: [ticket], overdue: [ticket], in_progress: [], completed_today: [], upcoming: [] } });
const ticketDetail = { status: "loaded", as_of: clock, ticket: { ...ticket, priority: "normal", requested_by: ticket.resident, routine: "housekeeping_room_service" },
  timeline: { requested: clock, started: null, finished: null, basis: "simulated", wait_minutes: null, work_minutes: null },
  outcome: "Waiting in the department queue for an available worker.",
  receipts: [{ receipt_id: "r1", action: "resident_request_created", status: "created", actor: { name: "SIM Resident 001", type: "simulated-agent" }, source: "canonical task service" }],
  history: [] };

function route(url) {
  if (url === "/simulator/community/dashboard") return Promise.resolve({ data: summary });
  const dept = url.match(/departments\/(.+)$/);
  if (dept) return Promise.resolve({ data: department(dept[1]) });
  if (url.includes("/tickets/")) return Promise.resolve({ data: ticketDetail });
  return Promise.reject(new Error("unexpected"));
}

async function mount(props = {}) {
  const container = document.createElement("div");
  const root = createRoot(container);
  await act(async () => root.render(<LiveDashboard {...props} />));
  return { container, root };
}

beforeEach(() => { api.get.mockImplementation(route); });

test("summary shows clock, counts and all eight department boxes", async () => {
  const { container, root } = await mount();
  expect(container.querySelector('[data-testid="dashboard-clock"]').textContent).toBe("Day 1 · 10:00");
  expect(container.querySelector('[data-testid="stat-overdue"]').textContent).toContain("1");
  expect(container.querySelectorAll('[data-testid^="dept-box-"]')).toHaveLength(8);
  act(() => root.unmount());
});

test("every department box opens its own detail, and Back returns", async () => {
  const { container, root } = await mount();
  for (const slug of SLUGS) {
    await act(async () => container.querySelector(`[data-testid="dept-box-${slug}"]`).click());
    expect(container.querySelector(`[data-testid="department-${slug}"]`)).not.toBeNull();
    expect(container.querySelector('[data-testid="department-waiting"]').textContent).toContain("housekeeping room service");
    await act(async () => container.querySelector('[data-testid="dashboard-back"]').click());
    expect(container.querySelector('[data-testid="dashboard-departments"]')).not.toBeNull();
  }
  act(() => root.unmount());
});

test("a ticket opens with its outcome, receipts and real ticket actions", async () => {
  const opened = [];
  const { container, root } = await mount({ onOpenRequest: (id) => opened.push(id) });
  await act(async () => container.querySelector('[data-testid="dept-box-housekeeping"]').click());
  await act(async () => container.querySelector('[data-testid="department-waiting"] [data-testid="ticket-t-wait"]').click());
  expect(container.querySelector('[data-testid="ticket-outcome"]').textContent).toContain("Waiting in the department queue");
  expect(container.querySelector('[data-testid="ticket-facts"]').textContent).toContain("Waiting so far1 h 15 min");
  expect(container.querySelector('[data-testid="ticket-receipts"]').textContent).toContain("resident request created");
  await act(async () => container.querySelector('[data-testid="ticket-open-actions"]').click());
  expect(opened).toEqual(["t-wait"]);
  act(() => root.unmount());
});

test("a failed read is reported, never shown as an empty community", async () => {
  api.get.mockImplementation(() => Promise.reject(new Error("network down")));
  const { container, root } = await mount();
  expect(container.querySelector('[data-testid="dashboard-read-error"]').textContent).toContain("network down");
  expect(container.querySelector('[data-testid="dashboard-departments"]')).toBeNull();
  act(() => root.unmount());
});

test("executor lag is stated plainly", async () => {
  api.get.mockImplementation((url) => url === "/simulator/community/dashboard"
    ? Promise.resolve({ data: { ...summary, run: { ...summary.run, clock: { absolute_minute: 700, day: 1, hh_mm: "11:40" }, executor_behind_minutes: 100 } } })
    : route(url));
  const { container, root } = await mount();
  expect(container.querySelector('[data-testid="dashboard-lag"]').textContent).toContain("1 h 40 min behind");
  act(() => root.unmount());
});
