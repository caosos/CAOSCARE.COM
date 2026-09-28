import React from "react";
import StatusPill from "./StatusPill";
import { VisualImage } from "./CapabilityVisuals";

// Every capability card opens its on-page panel. The thumbnail is the first
// visual that isn't a thin strip.
export default function CapabilityCard({ capability, onOpen, icon: Icon }) {
  const thumb = capability.visuals.find((v) => v.height / v.width > 0.3) || capability.visuals[0];
  return (
    <button type="button" onClick={() => onOpen(capability.id)} aria-haspopup="dialog"
            data-testid={`capability-card-${capability.id}`}
            className="group text-left h-full w-full min-w-0 bg-white rounded-2xl border border-caos-line overflow-hidden flex flex-col hover:border-caos-forest focus-visible:outline focus-visible:outline-2 focus-visible:outline-caos-forest transition-colors">
      {thumb && (
        <span className="block aspect-video bg-caos-ambient overflow-hidden">
          <VisualImage visual={thumb} className={`w-full h-full object-cover ${thumb.kind === "screen" ? "object-left-top" : "object-center"}`} />
        </span>
      )}
      <span className="p-5 md:p-6 flex flex-col flex-1">
        <span className="flex flex-wrap items-center gap-2">
          {Icon && <Icon className="w-5 h-5 text-caos-forest" strokeWidth={2} aria-hidden="true" />}
          <span className="font-display text-xl font-medium text-caos-forest">{capability.name}</span>
          <StatusPill status={capability.status} />
        </span>
        <span className="block text-caos-mute mt-3 leading-relaxed flex-1">{capability.summary}</span>
        <span className="mt-4 text-caos-forest font-medium underline underline-offset-4 decoration-caos-line group-hover:decoration-caos-forest">
          See how it works
        </span>
      </span>
    </button>
  );
}
