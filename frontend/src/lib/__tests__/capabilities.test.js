import { CAPABILITY_STATUS, STATUS_META, isDemonstrable, statusOf } from "../capabilities/status";
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

  // 2026-09-27 audit: only these have acceptance evidence. Changing this
  // list requires new evidence recorded in status.js and PROJECT_STATE.
  test("only evidence-backed capabilities are Working or In pilot", () => {
    const accepted = Object.entries(CAPABILITY_STATUS)
      .filter(([, s]) => isDemonstrable(s)).map(([id]) => id).sort();
    expect(accepted).toEqual(["lighting", "rf_pendant", "voice"]);
  });

  test("audited capabilities have the corrected status", () => {
    const expected = {
      one_press: "in_development", help: "in_development", nursing: "in_development",
      dining: "in_development", maintenance: "in_development", housekeeping: "in_development",
      administration: "in_development", reporting: "in_development", low_vision: "in_development",
      front_desk: "in_development", activities: "in_development", transportation: "in_development",
      escalation: "in_development", tv: "in_development", climate: "in_development",
      front_desk_calls: "planned", family_call: "planned", handset: "planned", community_calls: "planned",
    };
    for (const [id, s] of Object.entries(expected)) expect([id, statusOf(id)]).toEqual([id, s]);
  });
});

describe("demonstrations never outrun the evidence", () => {
  test("ids are unique across the site", () => {
    const ids = ALL.map((c) => c.id);
    expect(new Set(ids).size).toBe(ids.length);
  });

  test("accepted capabilities have five steps and a stated limitation", () => {
    for (const c of ALL.filter((x) => isDemonstrable(x.status))) {
      expect([c.id, c.steps?.length]).toEqual([c.id, STEP_TITLES.length]);
      if (c.status === "pilot") expect(c.limitation?.length).toBeGreaterThan(20);
    }
  });

  test("in-development and planned capabilities have no walkthrough, only a description", () => {
    for (const c of ALL.filter((x) => !isDemonstrable(x.status))) {
      expect([c.id, c.steps]).toEqual([c.id, undefined]);
      expect([c.id, (c.pending || "").length > 10]).toEqual([c.id, true]);
    }
  });

  test("For Communities covers every required department workflow", () => {
    const ids = COMMUNITY_WORKFLOWS.map((c) => c.id);
    for (const id of ["nursing", "maintenance", "transportation", "dining", "activities", "housekeeping",
      "therapy", "beauty", "front_desk", "administration", "escalation", "reporting"]) expect(ids).toContain(id);
  });

  test("dashboard rows only point at real workflows", () => {
    for (const r of DASHBOARD_ROWS) expect(COMMUNITY_BY_ID[r.workflow]).toBeTruthy();
  });

  test("no Aria quote promises arrival", () => {
    for (const c of ALL) for (const s of c.steps || []) {
      if (s.quote) expect(s.quote.toLowerCase()).not.toMatch(/on (the|their|her|his) way|coming|help is/);
    }
  });
});
