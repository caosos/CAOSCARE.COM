import React from "react";
import StatusPill from "./StatusPill";
import { STATUS_META, isDemonstrable } from "../../lib/capabilities/status";

function Heading({ capability, icon: Icon }) {
  return (
    <>
      {Icon && (
        <span className="w-12 h-12 rounded-xl bg-caos-ambient flex items-center justify-center mb-5">
          <Icon className="w-6 h-6 text-caos-forest" strokeWidth={2} />
        </span>
      )}
      <span className="flex flex-wrap items-center gap-2">
        <span className="font-display text-xl font-medium text-caos-forest">{capability.name}</span>
        <StatusPill status={capability.status} />
      </span>
      <span className="block text-caos-mute mt-3 leading-relaxed">{capability.summary}</span>
    </>
  );
}

// Accepted capabilities (working / in pilot) open a step-by-step demonstration
// on this page. Everything else expands in place into a labelled description:
// what exists today and what is not yet accepted, or the planned workflow.
export default function CapabilityCard({ capability, onOpen, icon }) {
  const box = "h-full w-full bg-white rounded-2xl p-6 md:p-8 border border-caos-line";
  if (isDemonstrable(capability.status) && capability.steps) {
    return (
      <button type="button" onClick={() => onOpen(capability.id)} aria-haspopup="dialog"
              data-testid={`capability-card-${capability.id}`}
              className={`group text-left flex flex-col hover:border-caos-forest focus-visible:outline focus-visible:outline-2 focus-visible:outline-caos-forest transition-colors ${box}`}>
        <Heading capability={capability} icon={icon} />
        <span className="flex-1" />
        <span className="mt-5 text-caos-forest font-medium underline underline-offset-4 decoration-caos-line group-hover:decoration-caos-forest">
          See how it works
        </span>
      </button>
    );
  }
  const planned = capability.status === "planned";
  return (
    <details className={`group ${box}`} data-testid={`capability-card-${capability.id}`}>
      <summary className="catalog-summary cursor-pointer list-none flex flex-col min-h-[48px]">
        <Heading capability={capability} icon={icon} />
        <span className="mt-5 text-caos-forest font-medium underline underline-offset-4 decoration-caos-line">
          <span className="group-open:hidden">{planned ? "See the planned design" : "See what's built so far"}</span>
          <span className="hidden group-open:inline">Hide details</span>
        </span>
      </summary>
      <div className="border-t border-caos-line pt-4 mt-4 space-y-3 text-caos-ink leading-relaxed">
        <p className="text-xs font-bold uppercase tracking-widest text-caos-mute">{STATUS_META[capability.status].meaning}</p>
        {capability.built && <p><b>Built so far:</b> {capability.built}</p>}
        <p><b>{planned ? "Planned:" : "Not yet accepted:"}</b> {capability.pending}</p>
      </div>
    </details>
  );
}
