import React from "react";
import PublicVisual from "./PublicVisual";
import StatusPill from "../capabilities/StatusPill";
import { SCREENS } from "../../lib/capabilities/visuals";
import { statusOf } from "../../lib/capabilities/status";

// What staff see (#162): the current Operations product, not the retired
// command-centre screens. Captured from a simulated community; no live records.
const SHOTS = [
  { visual: SCREENS.workspace, title: "My CAOSCare Workspace", body: "Each person arranges the boxes they need: calls waiting, work in progress, who is on duty, departments." },
  { visual: SCREENS.overview, title: "Operations overview", body: "What needs attention now, who owns it and how long it has waited." },
  { visual: SCREENS.recordsDrilldown, title: "Every number opens its records", body: "Click a box and see the exact requests behind it, with task IDs, period, timezone and status." },
];

export default function StaffShowcase({ compact = false, onOpen }) {
  const shots = compact ? [SHOTS[0], SHOTS[2]] : SHOTS;
  return (
    <div data-testid="staff-showcase">
      <div className="mb-6 flex flex-wrap items-center gap-3 text-[14px] text-[#4B5563]">
        <StatusPill status={statusOf("staff_dashboard")} />
        <span>Real CAOSCare screens · simulated 75-resident community, synthetic residents and staff.</span>
        {onOpen && (
          <button type="button" onClick={() => onOpen("staff_dashboard")} className="font-semibold text-[#1D4ED8] hover:underline" data-testid="staff-showcase-open">
            Limits and what's not accepted yet →
          </button>
        )}
      </div>
      <ul className={`grid grid-cols-1 gap-8 ${compact ? "md:grid-cols-2" : "lg:grid-cols-3"}`}>
        {shots.map((s) => (
          <li key={s.title} className="min-w-0">
            <h3 className="text-[19px] font-semibold text-[#111827]">{s.title}</h3>
            <p className="mt-1 mb-4 text-[15px] leading-relaxed text-[#4B5563]">{s.body}</p>
            <PublicVisual visual={s.visual} />
          </li>
        ))}
      </ul>
    </div>
  );
}
