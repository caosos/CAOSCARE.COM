import React from "react";
import useDashboardResource from "../../lib/useDashboardResource";
import { DUTY_LABEL, simTime, titleCase } from "../../lib/dashboardFormat";
import CoverShiftButton from "../simulator/CoverShiftButton";
import { Empty, PlannedList, ReadState, Section, TicketList } from "./DashboardParts";

function Person({ person, runId, onWorker, onTicket, onChanged }) {
  const shifts = (person.today || []).map((s) => `${titleCase(s.shift)} ${simTime(s.start)}–${s.end.hh_mm}${s.duty === "on_call" ? " (on call)" : ""}`);
  return (
    <li className="flex flex-wrap items-center justify-between gap-2 border-b border-caos-line p-2 last:border-0">
      <button type="button" className="min-w-0 text-left" onClick={() => onWorker(person.actor_id)} data-testid={`person-${person.actor_id}`}>
        <span className="block text-sm font-semibold text-caos-forest">{person.name}</span>
        <span className="block text-xs text-caos-mute">
          {titleCase(person.job_role)} · {shifts.length ? shifts.join("; ") : "Not scheduled today"}
          {person.covered_by ? ` · covered by ${person.covered_by}` : ""}
        </span>
      </button>
      <span className="flex items-center gap-2">
        {person.current && (
          <button type="button" className="text-xs text-caos-forest underline" onClick={() => onTicket(person.current.task_id)}>
            Working: {person.current.what}
          </button>
        )}
        {person.duty === "on_duty" && (
          <CoverShiftButton runId={runId} worker={{ ...person, department: person.department }} covered={!!person.covered_by} onChanged={onChanged} />
        )}
      </span>
    </li>
  );
}

function PeopleGroup({ title, rows, ...props }) {
  return (
    <Section title={title} count={rows.length}>
      {rows.length ? <ul className="rounded-lg border border-caos-line bg-white">{rows.map((p) => <Person key={p.actor_id} person={p} {...props} />)}</ul>
        : <Empty>Nobody.</Empty>}
    </Section>
  );
}

export default function DashboardDepartment({ id, runId, onWorker, onTicket, onChanged }) {
  const { data, error, stale, reload } = useDashboardResource(`/simulator/community/dashboard/departments/${id}`, 5000);
  if (!data) return error ? <ReadState error={error} /> : <p className="text-sm text-caos-mute">Loading department…</p>;
  const people = data.people.map((p) => ({ ...p, department: data.slug }));
  const groupProps = { runId, onWorker, onTicket, onChanged: () => { reload(); onChanged?.(); } };
  const work = data.work;
  return (
    <div className="space-y-5" data-testid={`department-${data.slug}`}>
      <ReadState error={error} stale={stale} />
      <div>
        <h2 className="font-display text-2xl text-caos-forest">{data.label}</h2>
        <p className="text-sm text-caos-mute">As of {simTime(data.as_of)} · Day {data.day}</p>
      </div>
      <div className="grid gap-4 lg:grid-cols-3">
        <PeopleGroup title={DUTY_LABEL.on_duty} rows={people.filter((p) => p.duty === "on_duty")} {...groupProps} />
        <PeopleGroup title={DUTY_LABEL.on_call} rows={people.filter((p) => p.duty === "on_call")} {...groupProps} />
        <PeopleGroup title={DUTY_LABEL.off_duty} rows={people.filter((p) => p.duty === "off_duty")} {...groupProps} />
      </div>
      <Section title="Today's shifts" count={data.schedule_today.length} testId="department-schedule">
        {data.schedule_today.length ? (
          <ul className="grid gap-1 text-sm sm:grid-cols-2">
            {data.schedule_today.map((s) => (
              <li key={`${s.actor_id}-${s.shift}-${s.start.absolute_minute}`} className="rounded border border-caos-line bg-white px-2 py-1">
                <b className="text-caos-forest">{simTime(s.start)}–{s.end.hh_mm}</b> {titleCase(s.shift)} · {s.name}{s.duty === "on_call" ? " (on call, off site)" : ""}
              </li>
            ))}
          </ul>
        ) : <Empty>No shifts today; the department is closed.</Empty>}
      </Section>
      <div className="grid gap-4 xl:grid-cols-2">
        <Section title="Overdue" count={work.overdue.length}><TicketList rows={work.overdue} onTicket={onTicket} empty="Nothing overdue." /></Section>
        <Section title="Waiting" count={work.waiting.length} testId="department-waiting"><TicketList rows={work.waiting} onTicket={onTicket} empty="Nobody is waiting." /></Section>
        <Section title="In progress" count={work.in_progress.length}><TicketList rows={work.in_progress} onTicket={onTicket} empty="Nothing in progress." /></Section>
        <Section title="Completed today (latest)" count={work.completed_today.length} testId="department-completed"><TicketList rows={work.completed_today} onTicket={onTicket} empty="Nothing completed yet today." /></Section>
      </div>
      <Section title="Upcoming today (planned, not yet requested)" count={work.upcoming.length}>
        <PlannedList rows={work.upcoming} />
      </Section>
    </div>
  );
}
