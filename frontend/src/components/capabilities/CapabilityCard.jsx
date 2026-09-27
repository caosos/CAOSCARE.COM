import React from "react";
import StatusPill from "./StatusPill";

// A capability card is a button: it opens the demonstration on this page.
export default function CapabilityCard({ capability, onOpen, icon: Icon }) {
  return (
    <button type="button" onClick={() => onOpen(capability.id)}
            data-testid={`capability-card-${capability.id}`}
            aria-haspopup="dialog"
            className="group text-left h-full w-full bg-white rounded-2xl p-6 md:p-8 border border-caos-line hover:border-caos-forest focus-visible:outline focus-visible:outline-2 focus-visible:outline-caos-forest transition-colors flex flex-col">
      {Icon && (
        <span className="w-12 h-12 rounded-xl bg-caos-ambient flex items-center justify-center mb-5">
          <Icon className="w-6 h-6 text-caos-forest" strokeWidth={2} />
        </span>
      )}
      <span className="flex flex-wrap items-center gap-2">
        <span className="font-display text-xl font-medium text-caos-forest">{capability.name}</span>
        <StatusPill status={capability.status} />
      </span>
      <span className="text-caos-mute mt-3 leading-relaxed flex-1">{capability.summary}</span>
      <span className="mt-5 text-caos-forest font-medium underline underline-offset-4 decoration-caos-line group-hover:decoration-caos-forest">
        See how it works
      </span>
    </button>
  );
}
