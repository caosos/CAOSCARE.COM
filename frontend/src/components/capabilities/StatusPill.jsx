import React from "react";
import { STATUS_META } from "../../lib/capabilities/status";

// The one look per public status, shared by the pill, the legend and the
// landing status board (LandingStatus), so a stage never has two colours.
export const STATUS_STYLE = {
  working: { pill: "bg-[#EFF6FF] text-[#1D4ED8] border-[#BFDBFE]", panel: "border-[#BFDBFE] bg-[#EFF6FF]", dot: "bg-[#2F80ED]" },
  pilot: { pill: "bg-[#F0FDF4] text-[#15803D] border-[#BBF7D0]", panel: "border-[#BBF7D0] bg-[#F0FDF4]", dot: "bg-[#16A34A]" },
  in_development: { pill: "bg-[#FFFBEB] text-[#B45309] border-[#FDE68A]", panel: "border-[#FDE68A] bg-[#FFFBEB]", dot: "bg-[#D97706]" },
  planned: { pill: "bg-white text-[#4B5563] border-[#D1D5DB]", panel: "border-[#E5E7EB] bg-white", dot: "bg-[#9CA3AF]" },
};

// The single status badge for every public page.
export default function StatusPill({ status, className = "" }) {
  const s = STATUS_META[status];
  if (!s) return null;
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-[12px] font-semibold ${STATUS_STYLE[status].pill} ${className}`}
          data-status={status}>
      <span className={`h-1.5 w-1.5 rounded-full ${STATUS_STYLE[status].dot}`} aria-hidden="true" />
      {s.label}
    </span>
  );
}
