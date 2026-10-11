const { rideLine, canRequestRide } = require("../rideLink");

test("ride line says only what the ride record says", () => {
  expect(rideLine(null)).toBeNull();
  expect(rideLine({ linked: false, ride: null })).toBeNull();
  expect(rideLine({ linked: true, ride: { status: "pending", booked: false, requested_for_date: "2026-10-15", requested_for_time_label: "2:00 PM", run: null } }))
    .toBe("Ride: requested for 2:00 PM · 2026-10-15, not yet booked");
  expect(rideLine({ linked: true, ride: { status: "pending", booked: true, run: { depart_time: "13:30", date: "2026-10-15", status: "scheduled", driver_name: "Demo - Pete Nash", vehicle_name: "Demo Van" } } }))
    .toBe("Ride: booked 13:30 with Demo - Pete Nash, Demo Van (2026-10-15)");
  expect(rideLine({ linked: true, ride: { status: "skipped", cancel_reason: "Appointment cancelled: out sick" } }))
    .toBe("Ride: cancelled — Appointment cancelled: out sick");
  expect(rideLine({ linked: true, ride: { status: "completed" } })).toBe("Ride: completed");
  expect(rideLine({ linked: true, ride: { status: "pending", booked: true, run: null, requested_for_date: "2026-10-15" } })).toContain("not yet booked");
});

test("a ride can be asked for only on an open, planned request with no open ride", () => {
  const planned = { resident_id: "r1", requested_for_date: "2026-10-15", status: "pending" };
  expect(canRequestRide(planned, undefined)).toBe(true);
  expect(canRequestRide({ ...planned, requested_for_date: null }, undefined)).toBe(false);
  expect(canRequestRide({ ...planned, resident_id: null }, undefined)).toBe(false);
  expect(canRequestRide({ ...planned, status: "completed" }, undefined)).toBe(false);
  expect(canRequestRide(planned, { linked: true, ride: { status: "pending" } })).toBe(false);
  expect(canRequestRide(planned, { linked: true, ride: { status: "skipped" } })).toBe(true);
});
