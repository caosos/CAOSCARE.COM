import React from "react";
import { Switch } from "../ui/switch";
import StatusPill from "../capabilities/StatusPill";

export default function RoomFeatureConfigurator({ features, selected, onToggle, onShow }) {
  return (
    <div data-testid="room-feature-configurator">
      <ul className="space-y-3">
        {features.map((f) => {
          const id = `feature-${f.id}`;
          return (
            <li key={f.id} className="bg-white rounded-2xl border border-caos-line p-4 flex items-start gap-4">
              <Switch id={id} checked={selected.has(f.id)} onCheckedChange={() => onToggle(f.id)}
                      className="mt-1 data-[state=checked]:bg-[var(--caos-forest)]" data-testid={id} />
              <label htmlFor={id} className="flex-1 cursor-pointer">
                <span className="flex flex-wrap items-center gap-2">
                  <span className="font-display text-lg font-medium text-caos-forest">{f.label}</span>
                  <StatusPill status={f.status} />
                </span>
                <span className="block text-caos-mute mt-1 leading-relaxed">{f.what}</span>
              </label>
              {onShow && (
                <button type="button" onClick={() => onShow(f.id)} aria-haspopup="dialog" data-testid={`feature-show-${f.id}`}
                        className="shrink-0 self-center text-sm font-medium text-caos-forest underline underline-offset-4 min-h-[44px] px-1">
                  See how it works
                </button>
              )}
            </li>
          );
        })}
      </ul>
      <p className="text-xs text-caos-mute mt-4">
        Status shows what CAOSCare has built today, not a commitment for any specific community.
      </p>
    </div>
  );
}
