import React from "react";
import { STATUS_META } from "../../lib/capabilities/status";

const TONE = {
  forest: "bg-caos-forest text-white",
  moss: "bg-caos-moss text-white",
  amber: "bg-caos-amber text-caos-ink",
  mute: "bg-white text-caos-mute border border-caos-line",
};

// The single status badge for every public page.
export default function StatusPill({ status, className = "" }) {
  const s = STATUS_META[status];
  if (!s) return null;
  return (
    <span className={`inline-block text-[11px] font-bold uppercase tracking-wider rounded-full px-2.5 py-1 ${TONE[s.tone]} ${className}`}
          data-status={status}>
      {s.label}
    </span>
  );
}
