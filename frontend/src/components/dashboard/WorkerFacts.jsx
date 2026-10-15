import React from "react";
import { titleCase } from "../../lib/dashboardFormat";
import { Section, TicketList } from "./DashboardParts";

// Role-specific facts for one simulated worker (#153 / #166). Every value comes from
// the worker-detail read; anything the simulator does not model is shown as unknown.
function RoleDetails({ details, onTicket }) {
  if (!details) return null;
  if (details.kind === "meal_service") {
    const served = Object.entries(details.served_today || {});
    return (
      <Section title="Meal service">
        <p className="text-sm">Now: {details.current_service || "not serving a meal right now"}</p>
        <p className="text-sm">Served today: {served.length ? served.map(([k, n]) => `${titleCase(k)} ${n}`).join(", ") : "none yet"}</p>
      </Section>
    );
  }
  if (details.kind === "cook") return <Section title="Kitchen work"><p className="text-sm">{details.note}</p></Section>;
  if (details.kind === "housekeeping") {
    return (
      <Section title="Room assignment">
        <p className="text-sm">{details.assigned_rooms || "No zone assigned"}</p>
        <p className="text-xs text-caos-mute">{details.note}</p>
      </Section>
    );
  }
  if (details.kind === "transportation") {
    return <Section title="Rides today"><p className="text-sm">{details.rides_today.length ? details.rides_today.join(", ") : "No rides today."}</p></Section>;
  }
  if (details.kind === "resident_care") {
    return <Section title="Residents cared for today"><p className="text-sm">{details.residents_today.join(", ") || "None yet today."}</p></Section>;
  }
  if (details.kind === "maintenance_queue") {
    return (
      <Section title={`Maintenance queue (oldest of ${details.open_queue_total})`} count={details.open_queue?.length}>
        <TicketList rows={details.open_queue || []} onTicket={onTicket} empty="No open maintenance requests." />
      </Section>
    );
  }
  return null;
}

export default function WorkerFacts({ data, onTicket }) {
  const today = data.today;
  return (
    <>
      <div className="flex flex-wrap gap-2 text-xs" data-testid="worker-facts">
        <span className="rounded-full bg-[#EDE9FE] px-2.5 py-0.5 font-semibold text-[#5B21B6]">SIMULATED</span>
        <span className="rounded-full bg-caos-paper px-2.5 py-0.5">{data.state_label}</span>
        <span className="rounded-full bg-caos-paper px-2.5 py-0.5">Break: not tracked (unknown)</span>
        <span className="rounded-full bg-caos-paper px-2.5 py-0.5">Location: not tracked (unknown)</span>
      </div>
      {today && (
        <Section title={`Today · Day ${today.day} (${today.weekday})`} count={today.assigned_total} testId="worker-today">
          <p className="mb-2 text-sm">{today.assigned_total} assigned today · {today.completed_total} completed today</p>
          <TicketList rows={today.assigned} onTicket={onTicket} empty="Nothing assigned today." />
        </Section>
      )}
      <RoleDetails details={data.role_details} onTicket={onTicket} />
      {data.week?.length > 0 && (
        <Section title="This week (planned rota)">
          <ul className="space-y-1 text-sm">
            {data.week.map((d) => (
              <li key={`${d.day}-${d.shift}`}>Day {d.day} {d.weekday} · {titleCase(d.shift)} {d.start}–{d.end}{d.duty === "on_call" ? " (on call)" : ""}</li>
            ))}
          </ul>
        </Section>
      )}
    </>
  );
}
