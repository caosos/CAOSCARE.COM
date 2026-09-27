import React from "react";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "../ui/dialog";
import StatusPill from "./StatusPill";
import { STATUS_META } from "../../lib/capabilities/status";
import { STEP_TITLES } from "../../lib/capabilities/steps";

function Step({ index, step }) {
  return (
    <li className="grid grid-cols-[2.5rem_1fr] gap-4">
      <span aria-hidden="true" className="w-10 h-10 rounded-full bg-caos-forest text-white font-display text-lg flex items-center justify-center">
        {index + 1}
      </span>
      <div className="pb-2">
        <h3 className="text-xs font-bold uppercase tracking-widest text-caos-mute">{STEP_TITLES[index]}</h3>
        <p className="mt-2 text-caos-ink leading-relaxed">{step.text}</p>
        {step.quote && (
          <p className="mt-3 font-display text-lg text-caos-forest border-l-4 border-caos-terracotta pl-4">"{step.quote}"</p>
        )}
        {step.sample && (
          <div className="mt-3 rounded-xl bg-white border border-caos-line p-4 font-mono text-sm text-caos-ink space-y-1">
            <p className="text-[10px] font-sans font-bold uppercase tracking-widest text-caos-mute">Sample data</p>
            {step.sample.map((line) => <p key={line}>{line}</p>)}
          </div>
        )}
      </div>
    </li>
  );
}

// Expanded demonstration of one capability. Full-screen panel on phones,
// centred dialog on larger screens; the page underneath keeps its scroll.
export default function CapabilityDemo({ capability, open, onClose, onCloseAutoFocus, footer }) {
  return (
    <Dialog open={open} onOpenChange={(v) => !v && onClose()}>
      {capability && (
        <DialogContent
          data-testid={`capability-demo-${capability.id}`}
          onCloseAutoFocus={onCloseAutoFocus}
          className="bg-caos-bone p-0 gap-0 w-full max-w-none h-[100dvh] rounded-none overflow-y-auto sm:h-auto sm:max-h-[90vh] sm:max-w-3xl sm:rounded-3xl"
        >
          <div className="p-6 md:p-10 pt-12 md:pt-10">
            <p className="text-xs font-bold uppercase tracking-widest text-caos-mute">Demonstration · sample data</p>
            <DialogTitle className="font-display text-3xl md:text-4xl font-normal text-caos-forest mt-3 pr-8">{capability.name}</DialogTitle>
            <div className="mt-3 flex flex-wrap items-center gap-3">
              <StatusPill status={capability.status} />
              <span className="text-sm text-caos-mute">{STATUS_META[capability.status].meaning}</span>
            </div>
            <DialogDescription className="mt-5 text-lg text-caos-ink">{capability.summary}</DialogDescription>
            {capability.parts && (
              <ul className="mt-5 flex flex-wrap gap-2" aria-label="Status of each part">
                {capability.parts.map((p) => (
                  <li key={p.id} className="flex items-center gap-2 rounded-full bg-white border border-caos-line pl-3 pr-1 py-1 text-sm">
                    {p.name} <StatusPill status={p.status} />
                  </li>
                ))}
              </ul>
            )}
            <ol className="mt-8 space-y-6">
              {capability.steps.map((step, i) => <Step key={STEP_TITLES[i]} index={i} step={step} />)}
            </ol>
            {footer}
            <button type="button" onClick={onClose}
                    className="mt-8 w-full sm:w-auto rounded-full border-2 border-caos-forest text-caos-forest px-6 py-3 min-h-[48px]">
              Close demonstration
            </button>
          </div>
        </DialogContent>
      )}
    </Dialog>
  );
}
