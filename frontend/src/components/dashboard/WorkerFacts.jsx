import React from "react";
import { titleCase } from "../../lib/dashboardFormat";
import { Section, TicketList } from "./DashboardParts";

const CLEAN_STATE = {
  completed: "Completed", in_progress: "In progress", remaining: "Remaining",
  not_simulated: "Not simulated (due before this run started)",
};

// Today's scheduled full cleans: room, housekeeper and canonical state (also used by the department view).
export function CleansToday({ rows, counts, onTicket }) {
  if (!rows) return null;
  return (
    <Section title="Full cleans scheduled today" count={rows.length} testId="cleans-today">
      {counts && <p className="text-sm">{counts.completed} completed · {counts.in_progress} in progress · {counts.remaining} remaining{counts.not_simulated ? ` · ${counts.not_simulated} not simulated (before run start)` : ""}</p>}
      {rows.length ? (
        <ul className="divide-y divide-caos-line rounded-lg border border-caos-line bg-white text-sm">
          {rows.map((r) => (
            <li key={r.room} className="flex flex-wrap justify-between gap-2 p-2">
              {r.task_id ? (
                <button type="button" className="text-left font-semibold text-caos-forest hover:underline" onClick={() => onTicket?.(r.task_id)}>{r.room}</button>
              ) : <span className="font-semibold">{r.room}</span>}
              <span className="text-caos-mute">{r.housekeeper_name} · {r.planned?.hh_mm} · {CLEAN_STATE[r.state]}</span>
            </li>
          ))}
        </ul>
      ) : <p className="text-sm text-caos-mute">No full cleans scheduled today.</p>}
    </Section>
  );
}

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
      <>
        <Section title="Room assignment">
          <p className="text-sm">{details.assigned_rooms || "No zone assigned"} · {details.occupied_rooms} occupied</p>
          <p className="text-xs text-caos-mute">{details.note}</p>
        </Section>
        <CleansToday rows={details.cleans_today} counts={details.cleans_today_counts} onTicket={onTicket} />
      </>
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
