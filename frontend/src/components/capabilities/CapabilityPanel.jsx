import React from "react";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "../ui/dialog";
import StatusPill from "./StatusPill";
import CapabilityVisuals from "./CapabilityVisuals";
import { STATUS_META } from "../../lib/capabilities/status";

const FLOW_HEADING = {
  working: "How it works",
  pilot: "How it works in the test room",
  in_development: "How it is designed to work · the full loop is not accepted yet",
  planned: "Planned design · not available yet",
};

const FLOW = [
  ["does", "What the resident or staff member does"],
  ["caos", "What CAOSCare does"],
  ["sees", "What staff see"],
  ["next", "What happens next"],
];

// The on-page experience for one capability: status, visuals, the flow,
// what is built today and what is not yet accepted. Full-screen on phones.
export default function CapabilityPanel({ capability, open, onClose, onCloseAutoFocus }) {
  return (
    <Dialog open={open} onOpenChange={(v) => !v && onClose()}>
      {capability && (
        <DialogContent data-testid={`capability-panel-${capability.id}`} onCloseAutoFocus={onCloseAutoFocus}
          className="bg-caos-bone p-0 gap-0 w-full max-w-none h-[100dvh] rounded-none overflow-y-auto overflow-x-hidden sm:h-auto sm:max-h-[92vh] sm:max-w-4xl sm:rounded-3xl">
          <div className="p-5 md:p-10 pt-12 md:pt-10 min-w-0">
            <DialogTitle className="font-display text-3xl md:text-4xl font-normal text-caos-forest pr-8">{capability.name}</DialogTitle>
            <div className="mt-3 flex flex-wrap items-center gap-3">
              <StatusPill status={capability.status} />
              <span className="text-sm text-caos-mute">{STATUS_META[capability.status].meaning}</span>
            </div>
            <DialogDescription className="mt-4 text-lg text-caos-ink">{capability.summary}</DialogDescription>
            {capability.limitation && (
              <p className="mt-4 rounded-xl bg-white border border-caos-line p-4 text-caos-ink"><b>Limits:</b> {capability.limitation}</p>
            )}
            <div className="mt-6"><CapabilityVisuals visuals={capability.visuals} /></div>
            <h3 className="mt-8 text-xs font-bold uppercase tracking-widest text-caos-mute" data-flow-heading={capability.status}>
              {FLOW_HEADING[capability.status]}
            </h3>
            <dl className="mt-4 grid grid-cols-1 md:grid-cols-2 gap-4">
              {FLOW.map(([key, label]) => (
                <div key={key} className="rounded-xl bg-white border border-caos-line p-4">
                  <dt className="text-xs font-bold uppercase tracking-widest text-caos-mute">{label}</dt>
                  <dd className="mt-2 text-caos-ink leading-relaxed">{capability.flow[key]}</dd>
                </div>
              ))}
            </dl>
            <div className="mt-6 grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="rounded-xl border border-caos-line p-4">
                <p className="text-xs font-bold uppercase tracking-widest text-caos-mute">Built today</p>
                <p className="mt-2 text-caos-ink">{capability.built}</p>
              </div>
              <div className="rounded-xl border border-caos-line p-4">
                <p className="text-xs font-bold uppercase tracking-widest text-caos-mute">
                  {capability.status === "planned" ? "Still planned" : "Not yet accepted"}
                </p>
                <p className="mt-2 text-caos-ink">{capability.pending}</p>
              </div>
            </div>
            <button type="button" onClick={onClose}
                    className="mt-8 w-full sm:w-auto rounded-full border-2 border-caos-forest text-caos-forest px-6 py-3 min-h-[48px]">
              Close
            </button>
          </div>
        </DialogContent>
      )}
    </Dialog>
  );
}
