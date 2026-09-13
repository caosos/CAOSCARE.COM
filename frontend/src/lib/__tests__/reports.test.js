import { exceptionKindLabel, exceptionTone, fmtHours, defaultWeekStart, buildQuery } from "../reports";

describe("exceptionKindLabel", () => {
  test("known kinds get a friendly label, unknown falls back", () => {
    expect(exceptionKindLabel("open_assistance_event")).toBe("Open assistance event");
    expect(exceptionKindLabel("overdue")).toBe("Overdue work");
    expect(exceptionKindLabel("something_new")).toBe("something new");
  });
});

describe("exceptionTone", () => {
  test("deterministic from kind + reason", () => {
    expect(exceptionTone({ kind: "open_assistance_event", reason: "Unacknowledged" })).toBe("critical");
    expect(exceptionTone({ kind: "open_assistance_event", reason: "Acknowledged, unresolved (open >72h - likely stale test data)" })).toBe("stale");
    expect(exceptionTone({ kind: "overdue", reason: "Overdue by 3h" })).toBe("warn");
    expect(exceptionTone({ kind: "failed_action", reason: "Operational action failed" })).toBe("warn");
    expect(exceptionTone({ kind: "unassigned_open", reason: "Unassigned - open 5d" })).toBe("info");
    expect(exceptionTone({ kind: "transportation_attention", reason: "no slot" })).toBe("info");
    expect(exceptionTone(null)).toBe("info");
  });
});

describe("fmtHours", () => {
  test("m / h / d thresholds", () => {
    expect(fmtHours(0)).toBe("0h");
    expect(fmtHours(-3)).toBe("0h");
    expect(fmtHours(0.5)).toBe("30m");
    expect(fmtHours(3)).toBe("3h");
    expect(fmtHours(47)).toBe("47h");
    expect(fmtHours(72)).toBe("3d");
    expect(fmtHours("nope")).toBe("0h");
  });
});

describe("defaultWeekStart", () => {
  test("N days before the given base, YYYY-MM-DD", () => {
    expect(defaultWeekStart(6, new Date("2026-09-07T12:00:00"))).toBe("2026-09-01");
    expect(defaultWeekStart(0, new Date("2026-09-07T12:00:00"))).toBe("2026-09-07");
  });
});

describe("buildQuery", () => {
  test("drops empty / null / undefined / 'all'", () => {
    expect(buildQuery({ date: "2026-09-07", department: "all", days: "" })).toBe("date=2026-09-07");
    expect(buildQuery({ a: 1, b: null, c: undefined, d: "x" })).toBe("a=1&d=x");
    expect(buildQuery(null)).toBe("");
  });
});
