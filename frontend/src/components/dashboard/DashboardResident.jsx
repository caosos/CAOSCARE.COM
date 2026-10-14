import React from "react";
import useDashboardResource from "../../lib/useDashboardResource";
import { simTime, titleCase } from "../../lib/dashboardFormat";
import { PlannedList, ReadState, Section, TicketList } from "./DashboardParts";

export default function DashboardResident({ id, onTicket }) {
  const { data, error, stale } = useDashboardResource(`/simulator/community/dashboard/residents/${encodeURIComponent(id)}`, 5000);
  if (!data) return error ? <ReadState error={error} /> : <p className="text-sm text-caos-mute">Loading resident…</p>;
  const p = data.profile;
  const req = data.requests;
  return (
    <div className="space-y-5" data-testid="resident-detail">
      <ReadState error={error} stale={stale} />
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="font-display text-2xl text-caos-forest">{p.name}</h2>
          <p className="text-sm text-caos-mute">
            Room {p.room}{p.occupant_slot ? ` (${p.occupant_slot})` : ""}{p.preferred_name ? ` · prefers "${p.preferred_name}"` : ""}
            {p.participation_level ? ` · ${titleCase(p.participation_level)}` : ""} · synthetic resident
          </p>
          {p.preferences && <p className="text-sm">Preferences: {String(p.preferences)}</p>}
        </div>
        <a href={`/admin?tab=residents&resident=${encodeURIComponent(p.resident_id)}`} className="text-sm text-caos-forest underline">
          Open resident profile
        </a>
      </div>
      <Section title={`Care and requests today (as of ${simTime(data.as_of)})`} count={data.care_today.done_or_open.length}>
        <TicketList rows={data.care_today.done_or_open} onTicket={onTicket} empty="Nothing requested yet today." />
      </Section>
      <Section title="Still planned today (planned, not yet requested)" count={data.care_today.upcoming.length}>
        <PlannedList rows={data.care_today.upcoming} />
      </Section>
      <div className="grid gap-4 xl:grid-cols-2">
        <Section title="Waiting" count={req.waiting.length}><TicketList rows={req.waiting} onTicket={onTicket} empty="No requests waiting." /></Section>
        <Section title="In progress" count={req.in_progress.length}><TicketList rows={req.in_progress} onTicket={onTicket} empty="Nothing in progress." /></Section>
      </div>
      <Section title={`Completed requests (latest of ${req.completed_total})`} count={req.completed.length}>
        <TicketList rows={req.completed} onTicket={onTicket} empty="No completed requests yet." />
      </Section>
    </div>
  );
}
