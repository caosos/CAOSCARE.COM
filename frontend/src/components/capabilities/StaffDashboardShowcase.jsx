import React from "react";
import { Link } from "react-router-dom";
import { VisualImage } from "./CapabilityVisuals";
import StatusPill from "./StatusPill";
import { SCREENS } from "../../lib/capabilities/visuals";
import { COMMUNITY_BY_ID } from "../../lib/capabilities/community";

// The public staff dashboard demo: real screenshots of the staff software,
// taken with sample data. Staff at a community use Staff sign in instead.
export default function StaffDashboardShowcase({ onOpen, compact = false }) {
  const dash = COMMUNITY_BY_ID.staff_dashboard;
  const shots = compact ? [SCREENS.staffDashboard] : [SCREENS.staffDashboard, SCREENS.requestsBoard];
  return (
    <div className="rounded-3xl bg-white border border-caos-line overflow-hidden" data-testid="staff-dashboard-demo">
      <div className="px-5 md:px-8 py-4 border-b border-caos-line bg-caos-ambient flex flex-wrap items-center justify-between gap-2">
        <span className="flex flex-wrap items-center gap-2">
          <span className="font-medium text-caos-forest">The CAOSCare staff software</span>
          <StatusPill status={dash.status} />
        </span>
        <span className="text-xs font-bold uppercase tracking-widest text-caos-mute">Demo · sample data, not live records</span>
      </div>
      <div className={`grid gap-4 p-4 md:p-6 ${shots.length > 1 ? "md:grid-cols-2" : ""}`}>
        {shots.map((s) => (
          <figure key={s.src} className="min-w-0">
            <button type="button" onClick={() => onOpen("staff_dashboard")} aria-haspopup="dialog"
                    className="block w-full rounded-xl overflow-hidden border border-caos-line hover:border-caos-forest">
              <VisualImage visual={s} className="w-full" />
            </button>
            <figcaption className="mt-2 text-sm text-caos-mute">{s.alt}</figcaption>
          </figure>
        ))}
      </div>
      <div className="px-5 md:px-8 py-4 border-t border-caos-line flex flex-wrap items-center gap-x-6 gap-y-2 text-sm">
        <button type="button" onClick={() => onOpen("staff_dashboard")} className="text-caos-forest font-medium underline underline-offset-4">
          See how the staff dashboard works
        </button>
        <span className="text-caos-mute">Staff at a community use <Link to="/login" className="underline underline-offset-4">Staff sign in</Link>.</span>
      </div>
    </div>
  );
}
