import { groupByDay, dayLabel, rideLineFor, lifecycleLabel, timeOf } from "../upcomingSchedule";

const rows = [
  { task_id: "c", requested_for_date: "2026-10-12", requested_for_time_label: "around 3 pm" },
  { task_id: "e", requested_for_date: "2026-10-12", requested_for_time_label: "afternoon" },
  { task_id: "b", requested_for_date: "2026-10-13", requested_for_time_label: "9:30 AM" },
  { task_id: "a", requested_for_date: "2026-10-13", requested_for_time_label: "2:00 PM", ride: { task_id: "r", status: "pending", booked: false, requested_for_date: "2026-10-13", requested_for_time_label: "2:00 PM", run: null } },
];

test("groups by day in the backend's order and keeps the order within a day", () => {
  const g = groupByDay(rows, "2026-10-11");
  expect(g.map((x) => x.date)).toEqual(["2026-10-12", "2026-10-13"]);
  expect(g[0].items.map((i) => i.task_id)).toEqual(["c", "e"]);
  expect(g[1].items.map((i) => i.task_id)).toEqual(["b", "a"]);
  expect(g[0].label.startsWith("Tomorrow")).toBe(true);
});

test("day labels: today, tomorrow, weekday + date, unscheduled", () => {
  expect(dayLabel("2026-10-11", "2026-10-11")).toBe("Today");
  expect(dayLabel("2026-10-12", "2026-10-11")).toMatch(/^Tomorrow, October 12$/);
  expect(dayLabel("2026-10-15", "2026-10-11")).toMatch(/^Thursday, October 15$/);
  expect(dayLabel(null, "2026-10-11")).toBe("Unscheduled");
});

test("row wording comes from the record: time, lifecycle, ride truth", () => {
  expect(timeOf({ scheduled_time_label: "10:00 AM" })).toBe("10:00 AM");
  expect(timeOf({})).toBe("time not set");
  expect(lifecycleLabel({ lifecycle: "acknowledged" })).toBe("Taken on");
  expect(rideLineFor(rows[3])).toBe("Ride: requested for 2:00 PM · 2026-10-13, not yet booked");
  expect(rideLineFor(rows[0])).toBeNull();
});
