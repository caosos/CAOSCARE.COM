import React from "react";
import { COMMUNITY_BY_ID, DASHBOARD_ROWS } from "../../lib/capabilities/community";
import StatusPill from "./StatusPill";

// Public staff dashboard demo: an illustrative layout of the staff board.
// Rows are sample data and not interactive; each shows its workflow's real
// development status.
export default function StaffDashboardPreview() {
  return (
    <div className="rounded-3xl bg-white border border-caos-line overflow-hidden" data-testid="staff-dashboard-demo">
      <div className="px-5 md:px-8 py-4 border-b border-caos-line bg-caos-ambient flex flex-wrap items-center justify-between gap-2">
        <p className="font-medium text-caos-forest">Sample Community · staff board</p>
        <p className="text-xs font-bold uppercase tracking-widest text-caos-mute">Illustrative layout · no resident data</p>
      </div>
      <ul className="divide-y divide-caos-line">
        {DASHBOARD_ROWS.map((r) => {
          const wf = COMMUNITY_BY_ID[r.workflow];
          return (
            <li key={r.id} className="px-5 md:px-8 py-4 grid grid-cols-[4.5rem_1fr] md:grid-cols-[4.5rem_5rem_1fr_11rem_9rem] gap-x-4 gap-y-1 items-center">
              <span className="font-mono text-sm text-caos-mute">{r.time}</span>
              <span className="font-medium">Room {r.room}</span>
              <span className="col-span-2 md:col-span-1">{r.text}</span>
              <span className="col-span-2 md:col-span-1 text-sm text-caos-mute">{wf.department} · {r.state}</span>
              <span className="col-span-2 md:col-span-1"><StatusPill status={wf.status} /></span>
            </li>
          );
        })}
      </ul>
      <p className="px-5 md:px-8 py-4 text-sm text-caos-mute border-t border-caos-line">
        This shows how the staff board is laid out. The badge on each row is that workflow's current stage; see the departments below for what is built and what is not yet accepted.
      </p>
    </div>
  );
}
