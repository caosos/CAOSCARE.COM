import React from "react";
import { Switch } from "../ui/switch";
import { FEATURE_STATUS } from "../../lib/roomExperience/features";

const TONE = {
  forest: "bg-caos-forest text-white",
  amber: "bg-caos-amber text-white",
  mute: "bg-caos-ambient text-caos-mute",
};

export function StatusBadge({ status }) {
  const s = FEATURE_STATUS[status];
  return (
    <span className={`text-[11px] font-bold uppercase tracking-wider rounded-full px-2.5 py-1 ${TONE[s.tone]}`}>
      {s.label}
    </span>
  );
}

export default function RoomFeatureConfigurator({ features, selected, onToggle }) {
  return (
    <div data-testid="room-feature-configurator">
      <ul className="space-y-3">
        {features.map((f) => {
          const id = `feature-${f.id}`;
          return (
            <li key={f.id} className="bg-white rounded-2xl border border-caos-line p-4 flex items-start gap-4">
              <Switch id={id} checked={selected.has(f.id)} onCheckedChange={() => onToggle(f.id)}
                      className="mt-1 data-[state=checked]:bg-[#153428]" data-testid={id} />
              <label htmlFor={id} className="flex-1 cursor-pointer">
                <span className="flex flex-wrap items-center gap-2">
                  <span className="font-display text-lg font-medium text-caos-forest">{f.label}</span>
                  <StatusBadge status={f.status} />
                </span>
                <span className="block text-caos-mute mt-1 leading-relaxed">{f.what}</span>
              </label>
            </li>
          );
        })}
      </ul>
      <p className="text-xs text-caos-mute mt-4">
        Status shows what CAOSCare has built today — not a commitment for any specific community.
      </p>
    </div>
  );
}
