import { logQuery, pickupLabel, LOG_STATUSES, LOG_STATUS_LABEL } from "../rideLog";

test("query drops empty filters and trims search", () => {
  expect(logQuery({ from: "2031-03-01", to: "2031-03-10", status: "", q: "  dana " })).toBe("from=2031-03-01&to=2031-03-10&q=dana");
});
test("every backend status has a label; pickup label handles none", () => {
  LOG_STATUSES.forEach((s) => expect(LOG_STATUS_LABEL[s]).toBeTruthy());
  expect(pickupLabel({})).toBe("-");
  expect(pickupLabel({ pickup_date: "2031-03-10", pickup_time: "08:30" })).toBe("2031-03-10 08:30");
});
