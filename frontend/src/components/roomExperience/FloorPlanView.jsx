import React from "react";
import { FEATURES_BY_ID } from "../../lib/roomExperience/features";

const KIND_LABEL = { window: "Window", tv: "TV", lamp: "Lamp", thermostat: "Thermostat", bed: "Bed", chair: "Chair" };
const FOREST = "#153428";
const MUTE = "#6B726A";

/** Which fixture kinds are "lit" by the currently selected features. */
function activeKinds(selected) {
  const kinds = new Set();
  for (const id of selected) for (const k of FEATURES_BY_ID[id]?.fixtures || []) kinds.add(k);
  return kinds;
}

export default function FloorPlanView({ model, selected }) {
  if (model.floorPlan?.imageUrl) {
    return (
      <figure className="m-0" data-testid="floorplan-image">
        <img src={model.floorPlan.imageUrl} alt={model.floorPlan.imageAlt}
             className="w-full rounded-2xl border border-caos-line bg-caos-surface" />
        <figcaption className="text-xs text-caos-mute mt-2">Published floor plan</figcaption>
      </figure>
    );
  }
  const lit = activeKinds(selected);
  const { rooms, fixtures } = model.schematic;
  return (
    <figure className="m-0" data-testid="floorplan-schematic">
      <svg viewBox="-2 -2 104 74" className="w-full rounded-2xl border border-caos-line bg-caos-surface"
           role="img" aria-label={`Schematic of ${model.name}: ${rooms.map((r) => r.label).join(", ")}`}>
        {rooms.map((r) => (
          <g key={r.id}>
            <rect x={r.x} y={r.y} width={r.w} height={r.h} fill="#F7F6F2" stroke={FOREST} strokeWidth="0.6" />
            <text x={r.x + 2} y={r.y + 5} fontSize="3" fill={MUTE}>{r.label}</text>
          </g>
        ))}
        {fixtures.map((f, i) => {
          const on = lit.has(f.kind);
          return (
            <g key={i}>
              <title>{KIND_LABEL[f.kind]}{on ? " — CAOSCare feature selected" : ""}</title>
              <circle cx={f.x} cy={f.y} r="2.6" fill={on ? FOREST : "#FFFFFF"} stroke={on ? FOREST : MUTE} strokeWidth="0.5" />
              <text x={f.x} y={f.y + 6} fontSize="2.6" textAnchor="middle" fill={on ? FOREST : MUTE}>{KIND_LABEL[f.kind]}</text>
            </g>
          );
        })}
      </svg>
      <figcaption className="text-xs text-caos-mute mt-2">
        Schematic, not to scale — filled markers are room objects with a CAOSCare feature switched on.
      </figcaption>
    </figure>
  );
}
