import { CAPABILITY_STATUS, STATUS_META, statusOf } from "../capabilities/status";
import { RESIDENT_CAPABILITIES } from "../capabilities/resident";
import { COMMUNITY_WORKFLOWS, COMMUNITY_BY_ID, DASHBOARD_ROWS } from "../capabilities/community";
import { STEP_TITLES } from "../capabilities/steps";
import { ROOM_FEATURES } from "../roomExperience/features";
import { RESIDENT_AREAS, WEARABLE_AREAS } from "../publicOnboarding";

const ALL = [...RESIDENT_CAPABILITIES, ...COMMUNITY_WORKFLOWS];

describe("capability status registry", () => {
  test("every registry entry uses a defined status", () => {
    for (const [id, s] of Object.entries(CAPABILITY_STATUS)) {
      expect([id, STATUS_META[s] ? "ok" : s]).toEqual([id, "ok"]);
    }
  });

  test("unknown capability ids fail loudly", () => {
    expect(() => statusOf("teleporter")).toThrow(/Unknown capability/);
  });

  test("every public surface takes its status from the registry", () => {
    const surfaces = [...ALL, ...ROOM_FEATURES, ...RESIDENT_AREAS, ...WEARABLE_AREAS];
    for (const c of surfaces) expect([c.id, c.status]).toEqual([c.id, CAPABILITY_STATUS[c.id]]);
  });

  test("lighting reads the same on /experience and in the room-controls demo", () => {
    const lighting = ROOM_FEATURES.find((f) => f.id === "lighting");
    const part = RESIDENT_CAPABILITIES.find((c) => c.id === "room_controls").parts.find((p) => p.id === "lighting");
    expect(lighting.status).toBe(part.status);
  });
});

describe("capability demonstrations", () => {
  test("ids are unique across the site", () => {
    const ids = ALL.map((c) => c.id);
    expect(new Set(ids).size).toBe(ids.length);
  });

  test("every demonstration has exactly the five steps, each with text", () => {
    for (const c of ALL) {
      expect([c.id, c.steps.length]).toEqual([c.id, STEP_TITLES.length]);
      for (const s of c.steps) expect(s.text.trim().length).toBeGreaterThan(10);
      expect(c.summary && c.name).toBeTruthy();
    }
  });

  test("For Communities covers every required department workflow", () => {
    const required = ["nursing", "maintenance", "transportation", "dining", "activities", "housekeeping",
      "therapy", "beauty", "front_desk", "administration", "escalation", "reporting"];
    expect(COMMUNITY_WORKFLOWS.map((c) => c.id).sort()).toEqual([...required].sort());
  });

  test("the resident side covers the requested capabilities", () => {
    const ids = RESIDENT_CAPABILITIES.map((c) => c.id);
    for (const id of ["one_press", "voice", "location", "low_vision", "rf_pendant", "room_controls"]) {
      expect(ids).toContain(id);
    }
  });

  test("dashboard rows only point at real workflows", () => {
    for (const r of DASHBOARD_ROWS) expect(COMMUNITY_BY_ID[r.workflow]).toBeTruthy();
  });

  test("no demonstration promises arrival: 'on the way' is never an Aria quote", () => {
    for (const c of ALL) for (const s of c.steps) {
      if (s.quote) expect(s.quote.toLowerCase()).not.toMatch(/on (the|their|her|his) way|coming now/);
    }
  });
});
