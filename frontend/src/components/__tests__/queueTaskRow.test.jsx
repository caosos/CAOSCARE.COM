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
