import { loadGroups, projectionText, utilPct, pct } from "../capacity";

test("load groups keep simulator traffic apart from resident and staff", () => {
  const g = loadGroups({ interval_s: 15, api: {
    resident_voice: { requests: 10 }, pendant_help: { requests: 2 }, staff_dashboard: { requests: 5 },
    simulator_resident: { requests: 30 }, simulator_staff: { requests: 3 }, receipt_audit_writes: { requests: 1 } } });
  expect(g).toEqual({ resident: 48, staff: 20, simulator: 132, background: 4 });
});

test("projection wording", () => {
  expect(projectionText(null)).toMatch(/No bottleneck/);
  expect(projectionText({ status: "insufficient_history", days_of_data: 1 })).toMatch(/Not enough history/);
  expect(projectionText({ status: "flat_or_falling" })).toMatch(/flat or falling/);
  expect(projectionText({ status: "rising", threshold: 0.8, projected_date: "2026-10-09", days_to_threshold: 5 }))
    .toMatch(/80% of its safe value around 2026-10-09/);
});

test("formatting", () => {
  expect(utilPct(0.856)).toBe("86%");
  expect(utilPct(null)).toBe("—");
  expect(pct(12.34)).toBe("12.3%");
});
