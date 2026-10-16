/** #168: "My tasks today" — readable rows, only the permitted next action, on-demand details. */
import React, { act } from "react";
import { createRoot } from "react-dom/client";

const mockGet = jest.fn();
jest.mock("../../lib/api", () => ({ api: { get: (...a) => mockGet(...a), post: jest.fn() } }));
jest.mock("@/lib/utils", () => ({ cn: (...a) => a.filter(Boolean).join(" ") }), { virtual: true });
jest.mock("../ui/dialog", () => ({ Dialog: () => null, DialogContent: () => null, DialogFooter: () => null,
                                   DialogHeader: () => null, DialogTitle: () => null }));
jest.mock("sonner", () => ({ toast: { success: jest.fn(), error: jest.fn() } }));
jest.mock("../RequestTimeline", () => (p) => require("react").createElement("div", { "data-testid": "timeline" }, `${p.receipts.length} receipts`));

const MyTasksCard = require("../MyTasksCard").default;
globalThis.IS_REACT_ACT_ENVIRONMENT = true;

test("loads the signed-in worker's tasks and offers only the permitted next action", async () => {
  mockGet.mockResolvedValue({ data: [
    { task_id: "a", title: "Night room check", status: "pending", priority: "normal", resident_name: "SIM Resident 003",
      room: "SIM-003", category: "nursing", created_at: "2026-10-15T03:41:00Z" },
    { task_id: "b", title: "Help to the bathroom", status: "in_progress", priority: "high", resident_name: "SIM Resident 004",
      room: "SIM-004", category: "nursing", created_at: "2026-10-15T03:45:00Z", started_at: "2026-10-15T04:40:00Z",
      resident_words: "I need help to the bathroom, please." },
  ] });
  const el = document.createElement("div");
  const root = createRoot(el);
  await act(async () => root.render(<MyTasksCard />));
  await act(async () => { await Promise.resolve(); });
  // the same request the workspace has always used for "my tasks"
  expect(mockGet).toHaveBeenCalledWith("/tasks", { params: { mine_only: true } });
  const text = el.textContent;
  for (const s of ["Night room check", "SIM Resident 003", "Room SIM-003", "Resident said", "2 open"]) expect(text).toContain(s);
  expect(el.querySelector("[data-testid=start-task-a]")).not.toBeNull();
  expect(el.querySelector("[data-testid=complete-task-a]")).toBeNull();
  expect(el.querySelector("[data-testid=complete-task-b]")).not.toBeNull();
  expect(el.querySelector("[data-testid=start-task-b]")).toBeNull();
  await act(async () => root.unmount());
});

const mine = { task_id: "m1", title: "Shower assistance", status: "in_progress", priority: "high", category: "nursing",
               resident_name: "SIM Resident 001", room: "SIM-001", assigned_name: "Pat Worker", notes: "Prefers warm water",
               created_at: "2026-10-14T15:00:00Z", started_at: "2026-10-14T15:05:00Z", simulated: true };
const simulation = { run_found: true, run_state: "RUNNING", expected_work_minutes: 20, origin: { label: "Scheduled routine" },
                     raised_by: { name: "SIM - Care Aide 01" }, now: { day: 1, hh_mm: "10:00" }, requested: { day: 1, hh_mm: "09:00" },
                     started: { day: 1, hh_mm: "09:40" }, finished: null, wait_reason: "none", waiting_minutes: 40, working_minutes: 20 };

test("a task's summary and its on-demand details (simulated clock, worker, notes, receipts)", async () => {
  mockGet.mockImplementation((url) => Promise.resolve(url === "/tasks" ? { data: [mine] }
    : { data: { task: mine, receipts: [{}, {}, {}], origin: simulation.origin, simulation } }));
  const el = document.createElement("div"); const root = createRoot(el);
  await act(async () => root.render(<MyTasksCard />));
  await act(async () => { await Promise.resolve(); });
  const row = el.querySelector("[data-testid=my-task-m1]").textContent;
  for (const s of ["Shower assistance", "SIM Resident 001", "Room SIM-001", "high", "(receipt time)", "next: complete it with what was done"]) expect(row).toContain(s);
  expect(mockGet).not.toHaveBeenCalledWith("/tasks/m1/detail");          // details load only when opened
  const details = el.querySelector("[data-testid=my-task-details-m1]");
  await act(async () => { details.open = true; details.dispatchEvent(new Event("toggle")); });
  await act(async () => { await Promise.resolve(); });
  expect(mockGet).toHaveBeenCalledWith("/tasks/m1/detail");
  const text = details.textContent;
  for (const s of ["Worker: Pat Worker", "Requested (sim)Day 1 09:00", "Expected~20 min", "Waited40 min · started Day 1 09:40",
                   "Working20 min", "Raised bySIM - Care Aide 01 (Scheduled routine)", "Notes: Prefers warm water", "3 receipts"]) expect(text).toContain(s);
  await act(async () => root.unmount());
});
