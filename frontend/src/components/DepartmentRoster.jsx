import { useEffect, useState } from "react";
import { api } from "../lib/api";

const DUTY = { on_duty: ["On duty", "bg-[#DCFCE7] text-[#166534]"], on_call: ["On call", "bg-[#FEF3C7] text-[#92400E]"],
               off_duty: ["Off duty", "bg-[#F3F4F6] text-[#6B7280]"], not_recorded: ["Shift not recorded", "bg-[#F3F4F6] text-[#6B7280]"] };
const AVAIL = { busy: "Busy", available: "Available", covered: "Covered by a person" };
const rank = (p) => ({ on_duty: 0, on_call: 1, not_recorded: 2, off_duty: 3 }[p.duty] ?? 4);
const roleLabel = (r) => (r || "").replace(/_/g, " ");

// Who works in this department: real staff (REAL) and the simulator's
// workers (SIM) from GET /departments/{slug}/roster — the same rota the
// simulator dashboard shows. Off-duty people are folded away.
export default function DepartmentRoster({ department, label, refreshKey }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(false);
  const [showOff, setShowOff] = useState(false);
  useEffect(() => {
    let live = true;
    api.get(`/departments/${department}/roster`)
      .then(({ data: d }) => {
        if (!live) return;
        if (Array.isArray(d?.people)) { setData(d); setError(false); } else { setError(true); }   // never crash on a malformed answer
      })
      .catch(() => live && setError(true));
    return () => { live = false; };
  }, [department, refreshKey]);

  if (error) return <p className="text-sm text-caos-terracotta" data-testid="dept-roster-error">Could not load who works in {label}.</p>;
  if (!data) return null;
  const people = [...data.people].sort((a, b) => rank(a) - rank(b) || a.name.localeCompare(b.name));
  const working = people.filter((p) => p.duty !== "off_duty");
  const off = people.filter((p) => p.duty === "off_duty");
  const sim = data.simulation;
  return (
    <section className="rounded-xl border border-caos-line bg-white" data-testid="dept-roster-panel">
      <header className="flex flex-wrap items-baseline justify-between gap-2 border-b border-caos-line px-4 py-2.5">
        <h3 className="text-[15px] font-semibold text-caos-ink">Who's working in {label}</h3>
        <span className="text-[13px] text-caos-mute">
          {data.on_duty} on duty · {data.real_count} REAL · {data.sim_count} SIM
          {sim ? ` · simulated day ${sim.day}, ${sim.as_of?.hh_mm} (${(sim.run_state || "").toLowerCase()})` : ""}
        </span>
      </header>
      {!people.length && (
        <p className="px-4 py-3 text-sm text-caos-terracotta" data-testid="dept-roster-empty">
          No one works in {label} yet. Add staff in Users &amp; access and set their department to {label}.
        </p>
      )}
      <ul className="divide-y divide-caos-line">
        {[...working, ...(showOff ? off : [])].map((p) => {
          const [dutyLabel, dutyTone] = DUTY[p.duty] || [p.duty, "bg-[#F3F4F6] text-[#6B7280]"];
          return (
            <li key={p.id} className="flex flex-wrap items-center gap-x-3 gap-y-1 px-4 py-2 text-[14px]" data-testid={`roster-${p.id}`}>
              <span className={`rounded px-1.5 py-0.5 text-[11px] font-bold ${p.kind === "sim" ? "bg-[#EDE9FE] text-[#5B21B6]" : "bg-[#DBEAFE] text-[#1E40AF]"}`}>
                {p.kind === "sim" ? "SIM" : "REAL"}
              </span>
              <span className="font-medium text-caos-ink">{p.name}</span>
              <span className="capitalize text-caos-mute">{roleLabel(p.job_role)}{p.shift ? ` · ${roleLabel(p.shift)} shift` : ""}</span>
              <span className={`rounded-full px-2 py-0.5 text-[12px] ${dutyTone}`}>{dutyLabel}</span>
              {AVAIL[p.availability] && p.duty !== "off_duty" && <span className="text-[13px] text-caos-mute">{AVAIL[p.availability]}</span>}
              {p.covered_by && <span className="text-[13px] text-caos-ink">· {p.covered_by} covering</span>}
              {p.current && <span className="min-w-0 truncate text-[13px] text-caos-ink">· Now: {p.current.title || p.current.task_id}</span>}
              {p.completed_today != null && <span className="ml-auto text-[13px] text-caos-mute">{p.completed_today} done today</span>}
            </li>
          );
        })}
      </ul>
      {off.length > 0 && (
        <button type="button" onClick={() => setShowOff((v) => !v)} className="w-full border-t border-caos-line px-4 py-2 text-left text-[13px] text-caos-forest hover:bg-caos-bone">
          {showOff ? "Hide" : "Show"} off duty ({off.length})
        </button>
      )}
      {data.note && <p className="border-t border-caos-line px-4 py-2 text-[12px] text-caos-mute">{data.note}</p>}
    </section>
  );
}
