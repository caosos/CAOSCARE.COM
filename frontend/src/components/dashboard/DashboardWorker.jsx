import React from "react";
import useDashboardResource from "../../lib/useDashboardResource";
import { DUTY_LABEL, simTime, titleCase } from "../../lib/dashboardFormat";
import CoverShiftButton from "../simulator/CoverShiftButton";
import { Empty, PlannedList, ReadState, Section, TicketList } from "./DashboardParts";
import WorkerFacts from "./WorkerFacts";

function Shifts({ rows }) {
  if (!rows?.length) return <Empty>Off.</Empty>;
  return (
    <ul className="space-y-1 text-sm">
      {rows.map((s) => (
        <li key={`${s.shift}-${s.start.absolute_minute}`}>
          {titleCase(s.shift)} · {simTime(s.start)} → {s.end.hh_mm}{s.duty === "on_call" ? " (on call, off site)" : ""}
        </li>
      ))}
    </ul>
  );
}

export default function DashboardWorker({ id, runId, onTicket, onChanged }) {
  const { data, error, stale, reload } = useDashboardResource(`/simulator/community/dashboard/workers/${encodeURIComponent(id)}`, 5000);
  if (!data) return error ? <ReadState error={error} /> : <p className="text-sm text-caos-mute">Loading worker…</p>;
  const w = data.worker;
  const availability = data.covered_by ? `Covered by ${data.covered_by}`
    : data.current.length ? "Busy" : DUTY_LABEL[data.duty] || titleCase(data.duty);
  return (
    <div className="space-y-5" data-testid="worker-detail">
      <ReadState error={error} stale={stale} />
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="font-display text-2xl text-caos-forest">{w.name}</h2>
          <p className="text-sm text-caos-mute">{titleCase(w.job_role)} · {w.department_label} · simulated worker</p>
          <p className="mt-1 text-sm"><b>{availability}</b>{data.shift_now ? ` · ${titleCase(data.shift_now)} shift` : ""} · as of {simTime(data.as_of)}</p>
        </div>
        {data.duty === "on_duty" && runId && (
          <CoverShiftButton runId={runId} worker={w} covered={!!data.covered_by} onChanged={() => { reload(); onChanged?.(); }} />
        )}
      </div>
      <WorkerFacts data={data} onTicket={onTicket} />
      <div className="grid gap-4 sm:grid-cols-2">
        <Section title="Shift today"><Shifts rows={data.schedule.today} /></Section>
        <Section title="Shift tomorrow"><Shifts rows={data.schedule.tomorrow} /></Section>
      </div>
      <Section title="Working on now" count={data.current.length}>
        <TicketList rows={data.current} onTicket={onTicket} empty="Not holding a ticket." />
      </Section>
      <Section title="Next planned work (planned, not yet done)" count={data.next_planned.length}>
        <PlannedList rows={data.next_planned} empty="No more planned work today or tomorrow." />
      </Section>
      <Section title={`Completed work (latest of ${data.completed_total})`} count={data.completed.length} testId="worker-completed">
        <TicketList rows={data.completed} onTicket={onTicket} empty="Nothing completed yet." />
      </Section>
    </div>
  );
}
