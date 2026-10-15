/** CO-008 compact row: the collapsed line carries the summary; actions, timeline and receipts appear on expand. */
import React, { act } from "react";
import { createRoot } from "react-dom/client";

const mockGet = jest.fn();
jest.mock("../../lib/api", () => ({ api: { get: (...a) => mockGet(...a) } }));
jest.mock("@/lib/utils", () => ({ cn: (...a) => a.filter(Boolean).join(" ") }), { virtual: true });
jest.mock("../ui/select", () => ({ Select: () => null, SelectContent: () => null, SelectItem: () => null, SelectTrigger: () => null, SelectValue: () => null }));
jest.mock("../RequestTimeline", () => (p) => require("react").createElement("div", { "data-testid": "timeline" }, `${p.receipts.length} receipts`));

const QueueTaskRow = require("../QueueTaskRow").default;
const { simDayOf } = require("../QueueTaskRow");
globalThis.IS_REACT_ACT_ENVIRONMENT = true;

const task = { task_id: "t1", title: "Morning room check", status: "pending", priority: "high", resident_name: "SIM Resident 004",
               room: "SIM-004", assigned_name: "SIM - Care Aide 05", created_at: new Date().toISOString(), simulated: true };
const ctx = { user: { user_id: "u1", role: "admin" }, act: jest.fn(), claim: jest.fn(), start: jest.fn(), assignTo: jest.fn(),
              review: { buttons: () => null }, isAdmin: true, canNote: () => true, canPlan: () => true, showAssign: false, roster: [],
              isOlder: () => false, requestRide: jest.fn(), openComplete: jest.fn(), openNote: jest.fn(), openPlan: jest.fn(),
              openCancel: jest.fn(), openHistory: jest.fn() };

test("collapsed shows the summary only; expanding shows actions and the timeline with receipts", async () => {
  mockGet.mockResolvedValue({ data: { task, receipts: [{}, {}] } });
  const el = document.createElement("div"); const root = createRoot(el);
  await act(async () => root.render(<QueueTaskRow t={task} ctx={ctx} />));
  const text = el.textContent;
  for (const s of ["Morning room check", "SIM Resident 004", "SIM-004", "high", "pending", "SIM - Care Aide 05"]) expect(text).toContain(s);
  expect(el.querySelector("[data-testid=wo-start-t1]")).toBeNull();
  expect(mockGet).not.toHaveBeenCalled();                       // nothing fetched until opened
  await act(async () => { el.querySelector("[data-testid=wo-row-t1]").click(); });
  await act(async () => { await Promise.resolve(); });
  expect(el.querySelector("[role=toolbar]")).not.toBeNull();
  for (const id of ["ack", "start", "note", "plan", "cancel", "history"]) expect(el.querySelector(`[data-testid=wo-${id}-t1]`)).not.toBeNull();
  // A waiting request is started before it can be completed (#168).
  expect(el.querySelector("[data-testid=wo-complete-t1]")).toBeNull();
  expect(mockGet).toHaveBeenCalledWith("/tasks/t1/detail");
  expect(el.querySelector("[data-testid=timeline]").textContent).toBe("2 receipts");
  await act(async () => root.unmount());
});

test("a simulator ticket shows its simulated day next to real time", () => {
  expect(simDayOf({ conversation_session_id: "simulator:event:day-012:resident-004:morning_room_check" })).toBe(13);
  expect(simDayOf({ conversation_session_id: "rt_abc" })).toBeNull();
});

test("expanded simulator ticket shows simulated request time beside receipt time, expected/elapsed, raiser and next step", async () => {
  const simulation = { run_found: true, run_state: "RUNNING", expected_work_minutes: 3, routine: "morning_room_check",
                       origin: { kind: "scheduled_routine", label: "Scheduled routine" }, raised_by: { name: "SIM - Care Aide 05" },
                       now: { day: 2, hh_mm: "08:10" }, requested: { day: 2, hh_mm: "07:40" }, started: null, finished: null,
                       wait_reason: "waiting_for_available_staff", waiting_minutes: 30, working_minutes: null };
  const long = { ...task, title: "Morning room check for SIM Resident 004 with a long description that must wrap" };
  mockGet.mockResolvedValue({ data: { task: long, receipts: [], origin: simulation.origin, simulation } });
  const el = document.createElement("div"); const root = createRoot(el);
  await act(async () => root.render(<QueueTaskRow t={long} ctx={ctx} />));
  await act(async () => { el.querySelector("[data-testid=wo-row-t1]").click(); });
  await act(async () => { await Promise.resolve(); });
  const facts = el.querySelector("[data-testid=wo-facts-t1]").textContent;
  expect(facts).toContain("Requested (sim)Day 2 07:40 · receipt time");
  expect(facts).toContain("Expected~3 min");
  expect(facts).toContain("Waiting30 min (waiting for available staff)");
  expect(facts).toContain("Raised bySIM - Care Aide 05 (Scheduled routine)");
  expect(facts).toContain("Next step: claim or start it when you begin the work");
  const title = Array.from(el.querySelectorAll("span")).find((s) => s.textContent === long.title);
  expect(title.className).not.toContain("truncate");                 // titles wrap when expanded
  await act(async () => root.unmount());
});

test("a real task shows why it exists and only real times - no simulation lines", async () => {
  const real = { ...task, simulated: false };
  mockGet.mockResolvedValue({ data: { task: real, receipts: [], origin: { kind: "staff_generated", label: "Staff / system created" }, simulation: null } });
  const el = document.createElement("div"); const root = createRoot(el);
  await act(async () => root.render(<QueueTaskRow t={real} ctx={ctx} />));
  await act(async () => { el.querySelector("[data-testid=wo-row-t1]").click(); });
  await act(async () => { await Promise.resolve(); });
  expect(el.querySelector("[data-testid=wo-facts-t1-sim]")).toBeNull();
  expect(el.querySelector("[data-testid=wo-facts-t1]").textContent).toContain("Why: Staff / system created");
  await act(async () => root.unmount());
});

test("only a request in progress offers Complete", async () => {
  mockGet.mockResolvedValue({ data: { task: {}, receipts: [] } });
  const el = document.createElement("div");
  const root = createRoot(el);
  await act(async () => root.render(<QueueTaskRow t={{ ...task, status: "in_progress" }} ctx={ctx} />));
  await act(async () => { el.querySelector("[data-testid=wo-row-t1]").click(); });
  expect(el.querySelector("[data-testid=wo-complete-t1]")).not.toBeNull();
  expect(el.querySelector("[data-testid=wo-start-t1]")).toBeNull();
  await act(async () => root.unmount());
});
