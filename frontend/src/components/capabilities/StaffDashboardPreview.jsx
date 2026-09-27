import React from "react";
import { COMMUNITY_BY_ID, DASHBOARD_ROWS } from "../../lib/capabilities/community";
import StatusPill from "./StatusPill";

// Public staff dashboard demo: a sample queue across departments. Each row
// opens that workflow's demonstration. No live data, no sign-in.
export default function StaffDashboardPreview({ onOpen }) {
  return (
    <div className="rounded-3xl bg-white border border-caos-line overflow-hidden">
      <div className="px-5 md:px-8 py-4 border-b border-caos-line bg-caos-ambient flex flex-wrap items-center justify-between gap-2">
        <p className="font-medium text-caos-forest">Sample Community · live board</p>
        <p className="text-xs font-bold uppercase tracking-widest text-caos-mute">Illustrative records · no resident data</p>
      </div>
      <ul className="divide-y divide-caos-line">
        {DASHBOARD_ROWS.map((r) => {
          const wf = COMMUNITY_BY_ID[r.workflow];
          return (
            <li key={r.id}>
              <button type="button" onClick={() => onOpen(r.workflow)} aria-haspopup="dialog"
                      data-testid={`dashboard-row-${r.id}`}
                      className="w-full text-left px-5 md:px-8 py-4 min-h-[56px] hover:bg-caos-ambient focus-visible:bg-caos-ambient grid grid-cols-[4.5rem_1fr] md:grid-cols-[4.5rem_5rem_1fr_11rem_9rem] gap-x-4 gap-y-1 items-center">
                <span className="font-mono text-sm text-caos-mute">{r.time}</span>
                <span className="font-medium md:order-none">Room {r.room}</span>
                <span className="col-span-2 md:col-span-1">{r.text}</span>
                <span className="col-span-2 md:col-span-1 text-sm text-caos-mute">{wf.department} · {r.state}</span>
                <span className="col-span-2 md:col-span-1"><StatusPill status={wf.status} /></span>
              </button>
            </li>
          );
        })}
      </ul>
      <p className="px-5 md:px-8 py-4 text-sm text-caos-mute border-t border-caos-line">
        Select a row to see how that request moves through CAOSCare. The badge shows that workflow's development stage.
      </p>
    </div>
  );
}
