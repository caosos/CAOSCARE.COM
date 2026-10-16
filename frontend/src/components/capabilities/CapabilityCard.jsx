import React from "react";
import StatusPill from "./StatusPill";
import { VisualImage, VISUAL_TAG } from "./CapabilityVisuals";

// Every capability card opens its on-page panel. The thumbnail is the
// capability's own first visual (a real screen or a labelled illustration), never
// a shared filler image; the label on it says which it is.
export default function CapabilityCard({ capability, onOpen }) {
  const thumb = capability.visuals.find((v) => v.height / v.width > 0.3) || capability.visuals[0];
  return (
    <button type="button" onClick={() => onOpen(capability.id)} aria-haspopup="dialog"
            data-testid={`capability-card-${capability.id}`}
            className="group flex h-full w-full min-w-0 flex-col overflow-hidden rounded-xl border border-[#E5E7EB] bg-white text-left shadow-[0_1px_2px_rgba(16,24,40,0.04)] hover:border-[#111827] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#2F80ED]">
      {thumb && (
        <span className="relative block aspect-video overflow-hidden border-b border-[#E5E7EB] bg-[#F9FAFB]">
          <VisualImage visual={thumb} className={`h-full w-full object-cover ${thumb.kind === "screen" ? "object-left-top" : "object-center"}`} />
          <span className="absolute bottom-2 left-2 rounded bg-white/95 px-2 py-0.5 text-[11px] font-medium text-[#4B5563] shadow-sm" data-visual-kind={thumb.kind}>
            {VISUAL_TAG[thumb.kind]}
          </span>
        </span>
      )}
      <span className="flex flex-1 flex-col p-5">
        <span className="flex flex-wrap items-center gap-2">
          <span className="text-[18px] font-semibold text-[#111827]">{capability.name}</span>
          <StatusPill status={capability.status} />
        </span>
        <span className="mt-2 block flex-1 text-[15px] leading-relaxed text-[#4B5563]">{capability.summary}</span>
        <span className="mt-4 text-[15px] font-semibold text-[#1D4ED8] group-hover:underline">See how it works →</span>
      </span>
    </button>
  );
}
