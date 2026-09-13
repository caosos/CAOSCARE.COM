import { formatAge, attentionAccent, accentStyle, linkTarget, departmentAlert } from "../opsOverview";

describe("formatAge", () => {
  test("buckets seconds into m / h / d", () => {
    expect(formatAge(0)).toBe("just now");
    expect(formatAge(59)).toBe("just now");
    expect(formatAge(60)).toBe("1m");
    expect(formatAge(3599)).toBe("59m");
    expect(formatAge(3600)).toBe("1h");
    expect(formatAge(90000)).toBe("1d");
    expect(formatAge(-5)).toBe("just now");
    expect(formatAge("7200")).toBe("2h");
  });
});

describe("attentionAccent", () => {
  test("tier / severity map to a stable accent", () => {
    expect(attentionAccent({ tier: 0, severity: "emergency" })).toBe("critical");
    expect(attentionAccent({ tier: 1, severity: "assist" })).toBe("warn");
    expect(attentionAccent({ tier: 3 })).toBe("warn");
    expect(attentionAccent({ tier: 5 })).toBe("info");
    expect(attentionAccent({ tier: 7 })).toBe("stale");
    expect(attentionAccent({ tier: 8 })).toBe("stale");
    expect(attentionAccent(null)).toBe("info");
  });
  test("accentStyle always returns a color triplet", () => {
    for (const a of ["critical", "warn", "info", "stale", "nonsense"]) {
      const s = accentStyle(a);
      expect(s).toHaveProperty("border");
      expect(s).toHaveProperty("bg");
      expect(s).toHaveProperty("text");
    }
  });
});

describe("linkTarget", () => {
  test("assistance -> alert board route; others -> admin tab", () => {
    expect(linkTarget("assistance")).toEqual({ type: "route", value: "/staff" });
    expect(linkTarget("requests")).toEqual({ type: "tab", value: "requests" });
    expect(linkTarget("transportation")).toEqual({ type: "tab", value: "transportation" });
    expect(linkTarget("tasks")).toEqual({ type: "tab", value: "tasks" });
    expect(linkTarget(undefined)).toEqual({ type: "tab", value: "tasks" });
  });
});

describe("departmentAlert", () => {
  test("surfaces overdue before unassigned, else null", () => {
    expect(departmentAlert({ overdue: 2, unassigned: 1 })).toBe("2 overdue");
    expect(departmentAlert({ overdue: 0, unassigned: 3 })).toBe("3 unassigned");
    expect(departmentAlert({ overdue: 0, unassigned: 0 })).toBe(null);
    expect(departmentAlert(null)).toBe(null);
  });
});
