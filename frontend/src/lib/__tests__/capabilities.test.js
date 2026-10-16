import fs from "fs";
import path from "path";
import { CAPABILITY_STATUS, STATUS_META, STATUS_ORDER, statusOf } from "../capabilities/status";
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

  // 2026-09-27 audit, 2026-10-12 owner direction, 2026-10-16 owner policy (PR #181): only
  // capabilities proven in the pilot architecture are public, all In pilot, with evidence in
  // status.js. Changing this list needs that evidence recorded in status.js and docs/PROJECT_STATE.md.
  test("the public site shows only Working and In pilot, never Planned or In development", () => {
    expect(STATUS_ORDER).toEqual(["working", "pilot"]);
    expect(Object.keys(STATUS_META).sort()).toEqual(["pilot", "working"]);
  });

  test("exactly the evidence-backed capabilities are public, all In pilot", () => {
    expect(Object.keys(CAPABILITY_STATUS).sort()).toEqual([
      "activities", "administration", "blinds", "climate", "dining", "escalation", "front_desk", "help",
      "housekeeping", "lighting", "low_vision", "maintenance", "nursing", "one_press", "rf_pendant",
      "room_screen", "staff_dashboard", "therapy", "transportation", "tv", "voice",
    ]);
    for (const [id, s] of Object.entries(CAPABILITY_STATUS)) expect([id, s]).toEqual([id, "pilot"]);
  });

  test("unproven capabilities are not listed at all", () => {
    // Owner 2026-10-16: removed, not relabelled. No phone system, family sharing, wearables,
    // building location or salon booking is built.
    for (const id of ["phone", "family_call", "front_desk_calls", "location", "wearables", "beauty"]) {
      expect([id, id in CAPABILITY_STATUS, !!CAPABILITIES_BY_ID[id]]).toEqual([id, false, false]);
    }
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
      expect(["screen", "illustration"]).toContain(v.kind);
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
      "housekeeping", "therapy", "front_desk", "administration", "escalation"]) expect(ids).toContain(id);
  });

  test("the resident side covers every required capability", () => {
    const ids = RESIDENT_CAPABILITIES.map((c) => c.id);
    for (const id of ["voice", "help", "lighting", "tv", "climate", "blinds", "rf_pendant", "low_vision", "room_screen"]) {
      expect(ids).toContain(id);
    }
  });

  test("every /experience room feature has a panel", () => {
    for (const f of ROOM_FEATURES) expect([f.id, !!CAPABILITIES_BY_ID[f.id]]).toEqual([f.id, true]);
  });

  test("no panel claims help is on the way", () => {
    for (const c of ALL_CAPABILITIES) {
      const text = Object.values(c.flow).join(" ").toLowerCase();
      expect([c.id, /help is (coming|on the way)|someone is on the way\b(?! unless)/.test(text)]).toEqual([c.id, false]);
    }
  });
});
