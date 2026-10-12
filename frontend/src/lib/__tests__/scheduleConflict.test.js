import { conflictDetail, conflictSummary, overridePayload } from "../scheduleConflict";

const c = { task_id: "a", what: "Knee physical therapy", category: "therapy", requested_for_time_label: "2:00 PM" };

test("a 409 schedule_conflict is recognised; other errors are not", () => {
  expect(conflictDetail({ response: { status: 409, data: { detail: { code: "schedule_conflict", conflicts: [c] } } } })).toBeTruthy();
  expect(conflictDetail({ response: { status: 409, data: { detail: "already skipped" } } })).toBeNull();
  expect(conflictDetail({ response: { status: 403, data: { detail: "Not allowed" } } })).toBeNull();
});

test("wording: overlap, not checked, undetermined, clear", () => {
  expect(conflictSummary({ checked: true, conflicts: [c] })).toBe("Overlaps Knee physical therapy (therapy) at 2:00 PM.");
  expect(conflictSummary({ checked: false, reason: "the planned time can't be read as a clock time, so overlap was not checked" })).toMatch(/^Overlap not checked: /);
  expect(conflictSummary({ checked: true, conflicts: [], undetermined: [c] })).toMatch(/1 other request that day has no readable time/);
  expect(conflictSummary({ checked: true, conflicts: [], undetermined: [] })).toBe("");
  expect(conflictSummary(null)).toBe("");
});

test("the save-anyway payload only adds the override flag", () => {
  expect(overridePayload({ requested_for_date: "2026-10-13", requested_for_time_label: "2:30 PM" })).toEqual({ requested_for_date: "2026-10-13", requested_for_time_label: "2:30 PM", conflict_override: true });
});

test("a staff double-booking names the room and what is shared", () => {
  const c = { what: "Gait training", category: "therapy", requested_for_time_label: "10:30 AM", kind: "staff",
              room: "214", shared: "provider Tess Ortiz PT" };
  expect(conflictSummary({ checked: true, conflicts: [c] }))
    .toBe("Overlaps Gait training (therapy) at 10:30 AM, room 214 — same provider Tess Ortiz PT.");
});
