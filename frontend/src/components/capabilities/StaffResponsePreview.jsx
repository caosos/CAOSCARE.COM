import React from "react";
import { Link } from "react-router-dom";
import { COMMUNITY_BY_ID, DASHBOARD_ROWS } from "../../lib/capabilities/community";

// Small resident-side look at what staff see. The full staff dashboard
// demonstration lives on /for-communities.
export default function StaffResponsePreview() {
  const rows = DASHBOARD_ROWS.slice(0, 3);
  return (
    <section aria-labelledby="staff-respond-heading" className="rounded-3xl bg-white border border-caos-line p-6 md:p-10">
      <p className="text-xs font-bold uppercase tracking-widest text-caos-mute">Illustrative layout · sample data</p>
      <h2 id="staff-respond-heading" className="font-display text-3xl text-caos-forest mt-2">How staff respond</h2>
      <p className="mt-3 max-w-2xl">When a resident asks for something, it is recorded in the right staff queue with the resident's own words. How staff work these queues day to day is still in development.</p>
      <ul className="mt-6 divide-y divide-caos-line border-y border-caos-line">
        {rows.map((r) => (
          <li key={r.id} className="py-3 flex flex-wrap gap-x-4 gap-y-1 items-baseline">
            <span className="font-mono text-sm text-caos-mute w-16">{r.time}</span>
            <span className="font-medium">Room {r.room}</span>
            <span className="flex-1 min-w-[12rem]">{r.text}</span>
            <span className="text-sm text-caos-mute">{COMMUNITY_BY_ID[r.workflow].department} · {r.state}</span>
          </li>
        ))}
      </ul>
      <Link to="/for-communities#dashboard" className="inline-block mt-6 text-caos-forest underline underline-offset-4">
        Open the staff dashboard demo
      </Link>
    </section>
  );
}
