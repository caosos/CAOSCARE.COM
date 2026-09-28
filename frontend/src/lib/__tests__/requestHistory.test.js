import { buildRequestTimeline, legacyNote } from "../requestHistory";

const base = { task_id: "t1", created_at: "2026-09-28T10:00:00Z", source: "aria_voice", status: "completed" };

test("event_log steps and every note appear in order with who did them", () => {
  const task = {
    ...base,
    notes: "done",
    duration_minutes: 12,
    completed_at: "2026-09-28T10:20:00Z",
    started_at: "2026-09-28T10:08:00Z",
    acknowledged_at: "2026-09-28T10:02:00Z",
    event_log: [
      { at: "2026-09-28T10:01:00Z", field: "re_request", to: 1, by: "resident", text: "is anyone coming?" },
      { at: "2026-09-28T10:02:00Z", field: "acknowledged", by: "u1", by_name: "Nurse Ana" },
      { at: "2026-09-28T10:03:00Z", field: "assigned_to", to: "u1", by: "u1", by_name: "Nurse Ana" },
      { at: "2026-09-28T10:08:00Z", field: "status", from: "pending", to: "in_progress", by: "u1", by_name: "Nurse Ana" },
      { at: "2026-09-28T10:10:00Z", field: "note", text: "walking to bathroom", by: "u1", by_name: "Nurse Ana" },
      { at: "2026-09-28T10:20:00Z", field: "note", text: "done", by: "u1", by_name: "Nurse Ana" },
      { at: "2026-09-28T10:20:00Z", field: "status", from: "in_progress", to: "completed", by: "u1", by_name: "Nurse Ana" },
    ],
  };
  const labels = buildRequestTimeline(task).map((e) => e.label);
  expect(labels).toEqual([
    "Created (aria voice)",
    "Resident asked again (2x)",
    "Acknowledged by Nurse Ana",
    "Claimed by Nurse Ana",
    "Started by Nurse Ana",
    "Note by Nurse Ana",
    "Note by Nurse Ana",
    "Completed by Nurse Ana · 12 min",
  ]);
  const notes = buildRequestTimeline(task).filter((e) => e.kind === "note").map((e) => e.text);
  expect(notes).toEqual(["walking to bathroom", "done"]);
  expect(legacyNote(task)).toBeNull();
});

test("a legacy task without event_log falls back to its own timestamps, nothing invented", () => {
  const task = {
    ...base,
    notes: "old note",
    acknowledged_at: "2026-09-28T10:02:00Z",
    acknowledged_by_name: "Nurse Ana",
    started_at: "2026-09-28T10:05:00Z",
    assigned_name: "Nurse Ana",
    completed_at: "2026-09-28T10:20:00Z",
    completed_by_name: "Nurse Ana",
  };
  const labels = buildRequestTimeline(task).map((e) => e.label);
  expect(labels).toEqual([
    "Created (aria voice)",
    "Acknowledged by Nurse Ana",
    "Started by Nurse Ana",
    "Completed by Nurse Ana",
  ]);
  expect(legacyNote(task)).toBe("old note");
});

test("a partial log only fills the steps it does not cover", () => {
  const task = {
    ...base,
    status: "in_progress",
    acknowledged_at: "2026-09-28T10:02:00Z",
    acknowledged_by_name: "Nurse Ana",
    started_at: "2026-09-28T10:05:00Z",
    event_log: [
      { at: "2026-09-28T10:05:00Z", field: "status", from: "pending", to: "in_progress", by: "u1", by_name: "Nurse Ana" },
    ],
  };
  const labels = buildRequestTimeline(task).map((e) => e.label);
  expect(labels).toEqual(["Created (aria voice)", "Acknowledged by Nurse Ana", "Started by Nurse Ana"]);
});

test("reassignment and unassignment read clearly", () => {
  const task = {
    ...base,
    status: "pending",
    event_log: [
      { at: "2026-09-28T10:01:00Z", field: "assigned_to", to: "u2", to_name: "Tech Bo", by: "u9", by_name: "Admin" },
      { at: "2026-09-28T10:02:00Z", field: "assigned_to", from: "u2", to: null, by: "u9", by_name: "Admin" },
    ],
  };
  const labels = buildRequestTimeline(task).map((e) => e.label);
  expect(labels).toEqual(["Created (aria voice)", "Assigned to Tech Bo by Admin", "Unassigned by Admin"]);
});

test("no task gives an empty timeline", () => {
  expect(buildRequestTimeline(null)).toEqual([]);
});
