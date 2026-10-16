import React from "react";
import { Link } from "react-router-dom";
import { ArrowLeft, Contrast } from "lucide-react";

// Top of the public demo room screen (#162 owner review 2026-10-16): the way
// back to the public site, and High Contrast shown as something to try, not
// just an "HC" chip. Uses the same toggle as the room screen's own HC button.
export default function DemoSiteBar({ highContrast, onToggleContrast }) {
  return (
    <div className="kiosk-demo-bar -mx-8 -mt-8 md:-mx-12 md:-mt-12 mb-8 border-b border-caos-line bg-white px-4 py-3 md:px-8"
         data-testid="demo-site-bar">
      <div className="mx-auto flex max-w-5xl flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-2">
          <Link to="/experience" data-testid="demo-back-experience"
                className="inline-flex min-h-[44px] items-center gap-2 rounded-lg bg-[#2F80ED] px-4 py-2 text-[15px] font-semibold text-white hover:bg-[#1F6FD9]">
            <ArrowLeft className="h-4 w-4" aria-hidden="true" /> Back to Explore a Room
          </Link>
          <Link to="/" data-testid="demo-back-home"
                className="inline-flex min-h-[44px] items-center rounded-lg border border-caos-line px-4 py-2 text-[15px] font-semibold text-caos-ink hover:border-caos-ink">
            CAOSCare home
          </Link>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <span className="hidden text-[14px] text-caos-mute sm:inline">Room screen demo · simulated devices</span>
          <button type="button" onClick={onToggleContrast} aria-pressed={highContrast} data-testid="demo-try-contrast"
                  className="inline-flex min-h-[44px] items-center gap-2 rounded-lg border-2 border-[#111827] bg-[#111827] px-4 py-2 text-[15px] font-semibold text-white hover:bg-[#1F2937]">
            <Contrast className="h-4 w-4" aria-hidden="true" />
            {highContrast ? "High contrast is on · turn off" : "Try high contrast for low vision"}
          </button>
        </div>
      </div>
    </div>
  );
}
