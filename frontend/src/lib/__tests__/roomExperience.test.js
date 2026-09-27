import { COMMUNITIES } from "../roomExperience/communities";
import { ROOM_FEATURES } from "../roomExperience/features";
import {
  availableFeatures, bedroomLabel, defaultSelection, formatSquareFeet, validateCommunities,
} from "../roomExperience/model";

const demoModel = COMMUNITIES[0].models[0];
const clone = (x) => JSON.parse(JSON.stringify(x));

describe("room experience data", () => {
  test("shipped community data passes every rule", () => {
    expect(validateCommunities(COMMUNITIES)).toEqual([]);
  });

  test("no invented real community: every entry is demo, or verified with a source", () => {
    for (const c of COMMUNITIES) {
      if (c.dataStatus === "verified") expect(c.source.url).toBeTruthy();
      else expect(c.dataStatus).toBe("demo");
    }
  });

  test("demo data must say so in its name", () => {
    const bad = clone(COMMUNITIES);
    bad[0].name = "Maple Grove";
    expect(validateCommunities(bad).join()).toMatch(/demo data must say so/);
  });

  test("verified data without a source is rejected", () => {
    const bad = clone(COMMUNITIES);
    bad[0].dataStatus = "verified";
    bad[0].name = "Real Place";
    expect(validateCommunities(bad).join()).toMatch(/verified data needs source/);
  });

  test("bad square footage, unknown fixture and missing alt text are caught", () => {
    const bad = clone(COMMUNITIES);
    bad[0].models[0].squareFeet = -5;
    bad[0].models[0].schematic.fixtures.push({ kind: "hot_tub", x: 1, y: 1 });
    bad[0].models[0].floorPlan = { imageUrl: "/media/floorplans/x.png", imageAlt: "" };
    const errs = validateCommunities(bad).join("\n");
    expect(errs).toMatch(/squareFeet/);
    expect(errs).toMatch(/unknown fixture kind hot_tub/);
    expect(errs).toMatch(/needs alt text/);
  });
});

describe("room experience helpers", () => {
  test("features follow the fixtures a model actually has", () => {
    const m = clone(demoModel);
    m.schematic.fixtures = [{ kind: "lamp", x: 1, y: 1 }];
    const ids = availableFeatures(m).map((f) => f.id);
    expect(ids).toContain("lighting");
    expect(ids).toContain("voice");            // "room" features always apply
    expect(ids).not.toContain("blinds");       // no window
    expect(ids).not.toContain("tv");
  });

  test("default selection = everything available", () => {
    expect([...defaultSelection(demoModel)].sort()).toEqual(availableFeatures(demoModel).map((f) => f.id).sort());
  });

  test("every feature has a phrase and a known status", () => {
    for (const f of ROOM_FEATURES) expect(f.phrase && f.label && f.status).toBeTruthy();
  });

  test("labels", () => {
    expect(formatSquareFeet(1250)).toBe("1,250 sq ft");
    expect(formatSquareFeet(null)).toBe("Square footage not published");
    expect(bedroomLabel({ bedrooms: 0, bathrooms: 1 })).toBe("Studio · 1 bath");
    expect(bedroomLabel({ bedrooms: 2, bathrooms: 2 })).toBe("2 bedrooms · 2 baths");
  });
});
