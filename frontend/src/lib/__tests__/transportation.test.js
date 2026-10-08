import { driverHoursLabel, runActions, riderStatusLabel, runStatusLabel, cleanTime } from "../transportation";

describe("driverHoursLabel", () => {
  test("no hours configured says so plainly", () => {
    expect(driverHoursLabel({ name: "A" })).toBe("No hours set - available any time");
  });
  test("days and shift", () => {
    expect(driverHoursLabel({ work_days: [1, 2, 3], shift_start: "08:00", shift_end: "16:00" })).toBe("Tue Wed Thu · 08:00–16:00");
  });
  test("shift without days means every day", () => {
    expect(driverHoursLabel({ shift_start: "07:00" })).toBe("Every day · 07:00–end of day");
  });
  test("an empty day list is not the same as unset", () => {
    expect(driverHoursLabel({ work_days: [] })).toBe("No working days");
  });
});

describe("runActions", () => {
  const rider = (status) => ({ task_id: status, status });
  test("confirmed run with open riders can depart and complete", () => {
    expect(runActions({ status: "confirmed", riders: [rider("pending")] }, { canOperate: true }))
      .toEqual({ depart: true, complete: true });
  });
  test("departed run can only complete", () => {
    expect(runActions({ status: "in_progress", riders: [rider("in_progress")] }, { canOperate: true }))
      .toEqual({ depart: false, complete: true });
  });
  test("no actions without operator rights", () => {
    expect(runActions({ status: "confirmed", riders: [rider("pending")] })).toEqual({ depart: false, complete: false });
  });
  test("no actions once every rider is closed", () => {
    expect(runActions({ status: "confirmed", riders: [rider("completed"), rider("skipped")] }, { canOperate: true }))
      .toEqual({ depart: false, complete: false });
  });
  test("no actions on a finished run", () => {
    expect(runActions({ status: "completed", riders: [rider("pending")] }, { canOperate: true }))
      .toEqual({ depart: false, complete: false });
  });
});

describe("labels", () => {
  test("rider labels", () => {
    expect(riderStatusLabel({ status: "pending" })).toBe("Booked");
    expect(riderStatusLabel({ status: "in_progress" })).toBe("On the ride");
    expect(riderStatusLabel({ status: "completed" })).toBe("Ride completed");
    expect(riderStatusLabel({ status: "skipped" })).toBe("Cancelled");
  });
  test("run labels", () => {
    expect(runStatusLabel({ status: "in_progress", closed_by_name: "Pete" })).toBe("Departed · Pete");
    expect(runStatusLabel({ status: "confirmed" })).toBe("Confirmed");
  });
  test("cleanTime", () => {
    expect(cleanTime("08:45")).toBe("08:45");
    expect(cleanTime("")).toBeNull();
    expect(cleanTime("9:30")).toBeNull();
  });
});

describe("transportStatusMessage", () => {
  const { transportStatusMessage } = require("../transportation");
  test("not found", () => expect(transportStatusMessage({ found: false })).toMatch(/no transportation request/));
  test("pending never claims a time", () => {
    const m = transportStatusMessage({ found: true, status: "pending", booked: false, purpose: "doctor appointment", requested_for_date: "2026-10-05", requested_for_time_label: "9:30" });
    expect(m).toMatch(/no confirmed pickup time/);
    expect(m).toMatch(/9:30/);
  });
  test("confirmed names the pickup, never 'on the way'", () => {
    const m = transportStatusMessage({ found: true, status: "pending", booked: true, purpose: "doctor appointment",
      run: { date: "2026-10-05", depart_time: "08:45", status: "confirmed", driver_name: "Pete", vehicle_name: "Van" } });
    expect(m).toBe("confirmed - the ride for doctor appointment: pickup at 08:45 on 2026-10-05 (driver Pete, Van).");
    expect(m).not.toMatch(/on the way/);
  });
  test("cancelled is not reported as waiting", () => {
    const m = transportStatusMessage({ found: true, status: "skipped", booked: false, purpose: "bank", requested_for_date: "2026-10-05", cancel_reason: "clinic moved it" });
    expect(m).toMatch(/was cancelled - reason noted: clinic moved it/);
    expect(m).not.toMatch(/waiting/);
  });
  test("completed and departed", () => {
    expect(transportStatusMessage({ found: true, status: "completed", booked: true, requested_for_date: "2026-10-05", run: { date: "2026-10-05", status: "completed" } })).toMatch(/completed/);
    expect(transportStatusMessage({ found: true, status: "in_progress", booked: true, requested_for_date: "2026-10-05", run: { date: "2026-10-05", depart_time: "08:45", status: "in_progress" } })).toMatch(/marked departed/);
  });
});

describe("ride history on the shared timeline", () => {
  const { buildRequestTimeline } = require("../requestHistory");
  test("book, change, depart, complete read as ride steps with detail", () => {
    const task = {
      created_at: "2026-10-01T10:00:00Z", source: "aria_voice", status: "completed",
      event_log: [
        { at: "2026-10-01T10:05:00Z", field: "ride_booked", by: "u1", by_name: "Dana", text: "Pickup 08:45 on 2026-10-05 · Pete, Van" },
        { at: "2026-10-02T09:00:00Z", field: "ride_changed", by: "u1", by_name: "Dana", text: "Pickup 09:00 on 2026-10-05 · Pete, Van" },
        { at: "2026-10-05T09:00:00Z", field: "status", from: "pending", to: "in_progress", by: "u2", by_name: "Pete" },
        { at: "2026-10-05T11:00:00Z", field: "status", from: "in_progress", to: "completed", by: "u2", by_name: "Pete" },
      ],
    };
    const labels = buildRequestTimeline(task).map((e) => [e.label, e.text || ""]);
    expect(labels).toEqual([
      ["Created (aria voice)", ""],
      ["Ride booked by Dana", "Pickup 08:45 on 2026-10-05 · Pete, Van"],
      ["Ride changed by Dana", "Pickup 09:00 on 2026-10-05 · Pete, Van"],
      ["Started by Pete", ""],
      ["Completed by Pete", ""],
    ]);
  });
});

import { rideBookedMessage, transportStatusMessage } from "../transportation";
import { buildRequestTimeline } from "../requestHistory";

describe("shared ride wording", () => {
  const run = { date: "2031-05-12", depart_time: "09:00" };
  test("a shared ride says it shares the run's pickup, and notes the asked time", () => {
    const m = rideBookedMessage({ run, shared: true }, { askedTime: "09:15" });
    expect(m).toContain("shares the 09:00 pickup");
    expect(m).toContain("you asked for 09:15");
    expect(m).not.toContain("booked for");
  });
  test("an unshared ride keeps the plain wording", () => {
    expect(rideBookedMessage({ run, shared: false })).toBe("confirmed - your ride is booked for 09:00 on 2031-05-12.");
  });
  test("a change uses the same shared wording", () => {
    expect(rideBookedMessage({ run, shared: true }, { changed: true })).toMatch(/^changed and confirmed - your ride shares the 09:00 pickup/);
  });
  test("status says shared pickup", () => {
    const m = transportStatusMessage({ found: true, status: "pending", booked: true, run: { ...run, status: "confirmed", shared: true } });
    expect(m).toContain("shares the 09:00 pickup");
  });
});

describe("ride timeline labels", () => {
  const ride = { task_id: "t", category: "transportation", created_at: "2031-05-12T08:00:00Z", status: "skipped",
    event_log: [
      { at: "2031-05-12T08:05:00Z", field: "assigned_to", to: "u1", by: "u1", by_name: "Pete", to_name: "Pete" },
      { at: "2031-05-12T08:06:00Z", field: "status", from: "pending", to: "in_progress", by: "u1", by_name: "Pete" },
      { at: "2031-05-12T08:07:00Z", field: "status", from: "in_progress", to: "skipped", by: "u1", by_name: "Pete" },
    ] };
  test("departed and cancelled read as rides, not generic steps", () => {
    const labels = buildRequestTimeline(ride).map((e) => e.label);
    expect(labels).toContain("Driver: Pete");
    expect(labels).toContain("Departed by Pete");
    expect(labels).toContain("Cancelled by Pete");
    expect(labels.join()).not.toMatch(/Skipped|Started|Claimed/);
  });
  test("other departments keep the generic labels", () => {
    const labels = buildRequestTimeline({ ...ride, category: "nursing" }).map((e) => e.label);
    expect(labels).toContain("Skipped by Pete");
    expect(labels).toContain("Started by Pete");
  });
});
