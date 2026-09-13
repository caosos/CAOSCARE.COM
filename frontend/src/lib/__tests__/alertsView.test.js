import { ageHours, isLikelyStale, alertTone, staleSummary, filterAlerts, STALE_HOURS } from "../alertsView";

const NOW = new Date("2026-09-07T12:00:00Z").getTime();
const hoursAgo = (h) => new Date(NOW - h * 3600_000).toISOString();

const A = [
  { alert_id: "a1", status: "active", severity: "emergency", created_at: hoursAgo(0.2) },
  { alert_id: "a2", status: "active", severity: "assist", created_at: hoursAgo(200) },   // stale
  { alert_id: "a3", status: "acknowledged", severity: "assist", created_at: hoursAgo(5) },
  { alert_id: "a4", status: "resolved", severity: "comfort", created_at: hoursAgo(30) },
  { alert_id: "a5", status: "acknowledged", severity: "comfort", created_at: hoursAgo(100) }, // stale
];

test("ageHours", () => {
  expect(ageHours(hoursAgo(3), NOW)).toBeCloseTo(3, 1);
  expect(ageHours(null)).toBe(0);
});

test("isLikelyStale: open AND older than 72h", () => {
  expect(isLikelyStale(A[0], NOW)).toBe(false);
  expect(isLikelyStale(A[1], NOW)).toBe(true);
  expect(isLikelyStale(A[3], NOW)).toBe(false); // resolved is never "stale-open"
  expect(isLikelyStale(A[4], NOW)).toBe(true);
  expect(STALE_HOURS).toBe(72);
});

test("alertTone", () => {
  expect(alertTone(A[0])).toBe("critical");
  expect(alertTone(A[2])).toBe("warn");
  expect(alertTone({ status: "active", severity: "comfort" })).toBe("info");
  expect(alertTone(A[3])).toBe("muted");
});

test("staleSummary splits open into live vs likely-stale, never counts resolved", () => {
  expect(staleSummary(A, NOW)).toEqual({ open_total: 4, likely_stale: 2, live: 2 });
});

test("filterAlerts: status + severity + hideStale, newest first", () => {
  expect(filterAlerts(A, { status: "active" }, NOW).map((a) => a.alert_id)).toEqual(["a1", "a2"]);
  expect(filterAlerts(A, { severity: "assist" }, NOW).map((a) => a.alert_id)).toEqual(["a3", "a2"]);
  expect(filterAlerts(A, { status: "all", hideStale: true }, NOW).map((a) => a.alert_id)).toEqual(["a1", "a3", "a4"]);
  expect(filterAlerts([], {}, NOW)).toEqual([]);
});
