import fs from "fs";
import path from "path";
import { CAPABILITY_STATUS, STATUS_META, isDemonstrable, statusOf } from "../capabilities/status";
import { RESIDENT_CAPABILITIES } from "../capabilities/resident";
import { COMMUNITY_WORKFLOWS } from "../capabilities/community";
import { ALL_CAPABILITIES, CAPABILITIES_BY_ID } from "../capabilities";
import { PHOTOS, SCREENS, PLACEHOLDERS } from "../capabilities/visuals";
import { ROOM_FEATURES } from "../roomExperience/features";

const PUBLIC = path.join(__dirname, "..", "..", "..", "public");

describe("capability status registry", () => {
  test("every registry entry uses a defined status", () => {
    for (const [id, s] of Object.entries(CAPABILITY_STATUS)) expect([id, !!STATUS_META[s]]).toEqual([id, true]);
  });

  test("unknown capability ids fail loudly", () => {
    expect(() => statusOf("teleporter")).toThrow(/Unknown capability/);
  });

  test("every public surface takes its status from the registry", () => {
    for (const c of [...ALL_CAPABILITIES, ...ROOM_FEATURES]) expect([c.id, c.status]).toEqual([c.id, CAPABILITY_STATUS[c.id]]);
  });

  // 2026-09-27 audit. Changing this list needs new acceptance evidence
  // recorded in status.js and docs/PROJECT_STATE.md.
  test("only evidence-backed capabilities are Working or In pilot", () => {
    const accepted = Object.entries(CAPABILITY_STATUS).filter(([, s]) => isDemonstrable(s)).map(([id]) => id).sort();
    expect(accepted).toEqual(["lighting", "rf_pendant", "room_screen", "voice"]);
  });

  test("audited capabilities keep their corrected status", () => {
    const expected = {
      one_press: "in_development", help: "in_development", nursing: "in_development", dining: "in_development",
      maintenance: "in_development", housekeeping: "in_development", administration: "in_development",
      low_vision: "in_development", front_desk: "in_development", activities: "in_development",
      transportation: "in_development", escalation: "in_development", tv: "in_development", climate: "in_development",
      staff_dashboard: "in_development", front_desk_calls: "planned", family_call: "planned", phone: "planned",
    };
    for (const [id, s] of Object.entries(expected)) expect([id, statusOf(id)]).toEqual([id, s]);
  });
});

describe("capability panels", () => {
  test("ids are unique across the site", () => {
    const ids = ALL_CAPABILITIES.map((c) => c.id);
    expect(new Set(ids).size).toBe(ids.length);
  });

  test("every panel has a title, summary, visual, full flow, built and pending text", () => {
    for (const c of ALL_CAPABILITIES) {
      expect([c.id, !!(c.name && c.summary)]).toEqual([c.id, true]);
      expect([c.id, c.visuals.length > 0]).toEqual([c.id, true]);
      for (const k of ["does", "caos", "sees", "next"]) expect([c.id, k, (c.flow[k] || "").length > 10]).toEqual([c.id, k, true]);
      expect([c.id, c.built.length > 5, c.pending.length > 5]).toEqual([c.id, true, true]);
      if (c.status === "pilot") expect([c.id, (c.limitation || "").length > 20]).toEqual([c.id, true]);
    }
  });

  test("every visual file exists and carries alt text", () => {
    for (const v of [...Object.values(SCREENS), ...Object.values(PHOTOS), ...Object.values(PLACEHOLDERS)]) {
      expect([v.src, fs.existsSync(path.join(PUBLIC, v.src))]).toEqual([v.src, true]);
      expect(v.alt.length).toBeGreaterThan(15);
      expect(["screen", "photo", "placeholder"]).toContain(v.kind);
    }
  });

  test("therapy and beauty shop show honest placeholders, not unrelated photos", () => {
    // Michael's 2026-09-27 review: the caregiver and bedroom photos did not
    // represent therapy or a salon.
    expect(CAPABILITIES_BY_ID.therapy.visuals).toEqual([PLACEHOLDERS.therapy]);
    expect(CAPABILITIES_BY_ID.beauty.visuals).toEqual([PLACEHOLDERS.beauty]);
  });

  test("staff departments show actual CAOSCare screens, not only photos", () => {
    for (const id of ["staff_dashboard", "nursing", "maintenance", "transportation", "dining", "activities",
      "housekeeping", "front_desk", "administration", "escalation"]) {
      expect([id, CAPABILITIES_BY_ID[id].visuals.some((v) => v.kind === "screen")]).toEqual([id, true]);
    }
  });

  test("For Communities covers every required department", () => {
    const ids = COMMUNITY_WORKFLOWS.map((c) => c.id);
    for (const id of ["staff_dashboard", "nursing", "maintenance", "transportation", "dining", "activities",
      "housekeeping", "therapy", "beauty", "front_desk", "administration", "escalation"]) expect(ids).toContain(id);
  });

  test("the resident side covers every required capability", () => {
    const ids = RESIDENT_CAPABILITIES.map((c) => c.id);
    for (const id of ["voice", "help", "lighting", "tv", "climate", "rf_pendant", "family_call", "phone", "room_screen"]) {
      expect(ids).toContain(id);
    }
  });

  test("every /experience room feature has a panel", () => {
    for (const f of ROOM_FEATURES) expect([f.id, !!CAPABILITIES_BY_ID[f.id]]).toEqual([f.id, true]);
  });

  test("planned capabilities are described as designs, not working features", () => {
    for (const c of ALL_CAPABILITIES.filter((x) => x.status === "planned")) {
      expect([c.id, /would|planned|not built/i.test(`${c.flow.caos} ${c.built} ${c.pending}`)]).toEqual([c.id, true]);
    }
  });

  test("no panel claims help is on the way", () => {
    for (const c of ALL_CAPABILITIES) {
      const text = Object.values(c.flow).join(" ").toLowerCase();
      expect([c.id, /help is (coming|on the way)|someone is on the way\b(?! unless)/.test(text)]).toEqual([c.id, false]);
    }
  });
});
