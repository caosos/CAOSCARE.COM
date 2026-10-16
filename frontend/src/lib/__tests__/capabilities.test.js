import fs from "fs";
import path from "path";
import { CAPABILITY_STATUS, STATUS_META, isDemonstrable, statusOf } from "../capabilities/status";
import { RESIDENT_CAPABILITIES } from "../capabilities/resident";
import { COMMUNITY_WORKFLOWS } from "../capabilities/community";
import { ALL_CAPABILITIES, CAPABILITIES_BY_ID } from "../capabilities";
import { ILLUSTRATIONS, SCREENS } from "../capabilities/visuals";
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

  // 2026-09-27 audit, 2026-10-12 owner direction (test-room/test-environment
  // evidence in status.js). Changing this list needs new acceptance evidence
  // recorded in status.js and docs/PROJECT_STATE.md.
  test("only evidence-backed capabilities are Working or In pilot", () => {
    const accepted = Object.entries(CAPABILITY_STATUS).filter(([, s]) => isDemonstrable(s)).map(([id]) => id).sort();
    expect(accepted).toEqual([
      "activities", "administration", "dining", "escalation", "front_desk", "help", "housekeeping", "lighting",
      "low_vision", "maintenance", "nursing", "one_press", "rf_pendant", "room_screen", "staff_dashboard",
      "therapy", "transportation", "tv", "voice",
    ]);
  });

  test("capabilities without test-room evidence stay below pilot", () => {
    const expected = {
      // 2026-10-16 re-audit (#162): climate's AC read-back is unverified; calling code exists but no
      // phone system is connected and no call was ever placed; the rest has no hardware or feature yet.
      climate: "in_development", front_desk_calls: "in_development", phone: "in_development",
      family_call: "planned", location: "planned",
      blinds: "planned", wearables: "planned", beauty: "planned",
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
    for (const v of [...Object.values(SCREENS), ...Object.values(ILLUSTRATIONS)]) {
      expect([v.src, fs.existsSync(path.join(PUBLIC, v.src))]).toEqual([v.src, true]);
      expect(v.alt.length).toBeGreaterThan(15);
      expect(["screen", "illustration", "concept"]).toContain(v.kind);
    }
  });

  test("no stale or orphan public media: every screen and illustration file is in the registry", () => {
    // #162: the 2026-09 command-centre screens and stock photos are retired, not left behind.
    const used = new Set([...Object.values(SCREENS), ...Object.values(ILLUSTRATIONS)].map((v) => v.src));
    for (const dir of ["screens", "illustrations"]) {
      for (const f of fs.readdirSync(path.join(PUBLIC, "media", dir))) expect(used).toContain(`/media/${dir}/${f}`);
    }
    for (const gone of ["marketing", "placeholders", "product"]) expect(fs.existsSync(path.join(PUBLIC, "media", gone))).toBe(false);
  });

  test("each card leads with its own picture, never a shared filler image", () => {
    // Michael 2026-10-15: no repeated generic room photo across unrelated capability cards.
    for (const group of [RESIDENT_CAPABILITIES, COMMUNITY_WORKFLOWS]) {
      const leads = group.map((c) => c.visuals[0].src);
      expect(new Set(leads).size).toBe(leads.length);
    }
  });

  test("planned capabilities lead with a labelled concept, built ones never do", () => {
    for (const c of ALL_CAPABILITIES) {
      const lead = c.visuals[0].kind;
      if (c.status === "planned") expect([c.id, lead]).toEqual([c.id, "concept"]);
      if (c.status === "pilot" || c.status === "working") expect([c.id, lead === "concept"]).toEqual([c.id, false]);
    }
  });

  test("the low-vision card shows the real low-vision screen first", () => {
    expect([SCREENS.roomContrast, SCREENS.roomEnlarged]).toContain(CAPABILITIES_BY_ID.low_vision.visuals[0]);
    expect(SCREENS.roomContrast.kind).toBe("screen");
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
