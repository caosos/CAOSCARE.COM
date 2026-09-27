import { FEATURE_STATUS, ROOM_FEATURES } from "./features";

const FIXTURE_KINDS = new Set(["window", "tv", "lamp", "thermostat", "bed", "chair"]);

/** Features this model can offer: those whose fixtures exist in its room ("room" always does). */
export function availableFeatures(model) {
  const kinds = new Set(["room", ...model.schematic.fixtures.map((f) => f.kind)]);
  return ROOM_FEATURES.filter((f) => f.fixtures.some((k) => kinds.has(k)));
}

export function defaultSelection(model) {
  return new Set(availableFeatures(model).map((f) => f.id));
}

export function formatSquareFeet(n) {
  return typeof n === "number" ? `${n.toLocaleString("en-US")} sq ft` : "Square footage not published";
}

export function bedroomLabel(model) {
  const bed = model.bedrooms === 0 ? "Studio" : `${model.bedrooms} bedroom${model.bedrooms > 1 ? "s" : ""}`;
  return `${bed} · ${model.bathrooms} bath${model.bathrooms === 1 ? "" : "s"}`;
}

/** Every data rule in communities.js; returns a list of problems (empty = valid). */
export function validateCommunities(communities) {
  const errors = [];
  const ids = new Set();
  const seen = (id, where) => {
    if (!id) errors.push(`${where}: missing id`);
    else if (ids.has(id)) errors.push(`${where}: duplicate id ${id}`);
    ids.add(id);
  };
  for (const c of communities) {
    const where = `community ${c.id}`;
    seen(c.id, where);
    if (c.dataStatus === "demo") {
      if (!/demo|sample/i.test(c.name)) errors.push(`${where}: demo data must say so in its name`);
    } else if (c.dataStatus === "verified") {
      const s = c.source || {};
      if (!s.publisher || !s.url || !s.retrievedAt) {
        errors.push(`${where}: verified data needs source.publisher, source.url and source.retrievedAt`);
      }
    } else {
      errors.push(`${where}: dataStatus must be "demo" or "verified"`);
    }
    if (!c.models?.length) errors.push(`${where}: no models`);
    for (const m of c.models || []) {
      const mw = `model ${m.id}`;
      seen(m.id, mw);
      if (m.squareFeet !== null && !(typeof m.squareFeet === "number" && m.squareFeet > 0)) {
        errors.push(`${mw}: squareFeet must be a positive number or null`);
      }
      if (m.floorPlan?.imageUrl && !m.floorPlan.imageAlt) errors.push(`${mw}: floor-plan image needs alt text`);
      const roomIds = new Set((m.schematic?.rooms || []).map((r) => r.id));
      if (!roomIds.size) errors.push(`${mw}: schematic has no rooms`);
      for (const f of m.schematic?.fixtures || []) {
        if (!FIXTURE_KINDS.has(f.kind)) errors.push(`${mw}: unknown fixture kind ${f.kind}`);
      }
    }
  }
  for (const f of ROOM_FEATURES) {
    if (!FEATURE_STATUS[f.status]) errors.push(`feature ${f.id}: unknown status ${f.status}`);
  }
  return errors;
}
