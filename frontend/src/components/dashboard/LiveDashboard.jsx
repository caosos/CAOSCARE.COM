import React, { useEffect, useRef, useState } from "react";
import { Badge } from "../ui/badge";
import { Card } from "../ui/card";
import useDashboardResource from "../../lib/useDashboardResource";
import { AVAILABILITY_LABEL, DUTY_LABEL, minutes, observedPace, simTime, titleCase } from "../../lib/dashboardFormat";
import { BackBar, Empty, ReadState, Section, Stat } from "./DashboardParts";
import DashboardDepartment from "./DashboardDepartment";
import DashboardWorker from "./DashboardWorker";
import DashboardResident from "./DashboardResident";
import DashboardTicket from "./DashboardTicket";

const STATE_CLASS = { RUNNING: "border-caos-moss text-caos-forest", PAUSED: "border-caos-amber text-[#8B5A20]" };

function usePace(clock) {
  const previous = useRef(null);
  const [pace, setPace] = useState(null);
  useEffect(() => {
    if (clock?.absolute_minute === undefined) return;
    const now = { minute: clock.absolute_minute, at: Date.now() };
    if (previous.current && now.at - previous.current.at >= 4000) {
      setPace(observedPace(previous.current, now));
      previous.current = now;
    } else if (!previous.current) {
      previous.current = now;
    }
  }, [clock?.absolute_minute]);
  return pace;
}

function Header({ run, pace }) {
  return (
    <div className="flex flex-wrap items-start justify-between gap-3">
      <div>
        <p className="text-xs font-bold uppercase tracking-widest text-caos-mute">Simulated community · 75 residents</p>
        <p className="font-display text-3xl text-caos-forest" data-testid="dashboard-clock">{simTime(run.as_of)}</p>
        <p className="text-xs text-caos-mute">
          {pace ? `Running at about ${pace}× real time (measured)` : "Measuring pace…"}
          {run.progress_percent !== null ? ` · ${run.progress_percent}% of the 90-day plan` : ""}
        </p>
      </div>
      <Badge variant="outline" className={STATE_CLASS[run.state] || "text-caos-mute"} data-testid="dashboard-state">
        {run.state || "UNKNOWN"}
      </Badge>
      {run.executor_behind_minutes > 0 && (
        <p className="w-full rounded-lg border border-caos-amber bg-[#FDF3E3] p-2 text-sm" data-testid="dashboard-lag">
          The simulation clock reads {simTime(run.clock)}, but work has only been carried out up to {simTime(run.as_of)}
          ({minutes(run.executor_behind_minutes)} behind). Everything here is shown as of {simTime(run.as_of)}.
        </p>
      )}
    </div>
  );
}

function DepartmentBox({ dept, onOpen }) {
  const alert = dept.status === "uncovered" || dept.overdue > 0;
  return (
    <button type="button" onClick={() => onOpen(dept.slug)} data-testid={`dept-box-${dept.slug}`}
            className={`rounded-xl border bg-white p-4 text-left shadow-sm hover:border-caos-moss ${alert ? "border-caos-terracotta" : "border-caos-line"}`}>
      <span className="flex items-start justify-between gap-2">
        <span className="font-semibold text-caos-forest">{dept.label}</span>
        <span className="text-xs text-caos-mute">{DUTY_LABEL[dept.status] || titleCase(dept.status)}</span>
      </span>
      <span className="mt-1 block text-xs text-caos-mute">
        {dept.on_duty} on duty{dept.on_call ? ` · ${dept.on_call} on call` : ""} · hours {dept.hours}
      </span>
      <span className="mt-3 grid grid-cols-4 gap-1 text-center text-xs">
        {[["Waiting", dept.waiting], ["Working", dept.in_progress], ["Done today", dept.completed_today], ["Overdue", dept.overdue]].map(([label, value]) => (
          <span key={label} className="rounded bg-caos-mute/5 py-1">
            <span className={`block font-display text-lg ${label === "Overdue" && value ? "text-caos-terracotta" : "text-caos-forest"}`}>{value}</span>
            {label}
          </span>
        ))}
      </span>
    </button>
  );
}

function PeopleList({ rows, onOpen, kind }) {
  if (!rows?.length) return <Empty>None.</Empty>;
  return (
    <ul className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3" data-testid={`dashboard-${kind}-list`}>
      {rows.map((row) => (
        <li key={row.actor_id || row.resident_id}>
          <button type="button" onClick={() => onOpen(row.actor_id || row.resident_id)}
                  className="w-full rounded-lg border border-caos-line bg-white p-2 text-left text-sm hover:border-caos-moss">
            <span className="block font-semibold text-caos-forest">{row.name}</span>
            <span className="block text-xs text-caos-mute">
              {kind === "staff"
                ? `${titleCase(row.department)} · ${titleCase(row.job_role)} · ${AVAILABILITY_LABEL[row.availability] || titleCase(row.availability)}${row.covered_by ? ` by ${row.covered_by}` : ""}`
                : `${row.room} · ${row.open_requests} open request${row.open_requests === 1 ? "" : "s"}`}
            </span>
          </button>
        </li>
      ))}
    </ul>
  );
}

export default function LiveDashboard({ onOpenRequest }) {
  const { data, error, stale, reload } = useDashboardResource("/simulator/community/dashboard", 2000);
  const [stack, setStack] = useState([]);
  const pace = usePace(data?.run?.clock);
  const view = stack[stack.length - 1];
  const open = (kind, id) => setStack((s) => [...s, { kind, id }]);
  const back = () => setStack((s) => s.slice(0, -1));
  const nav = { onDepartment: (id) => open("department", id), onWorker: (id) => open("worker", id),
                onResident: (id) => open("resident", id), onTicket: (id) => open("ticket", id) };

  if (!data && !error) return <Card className="p-4" data-testid="dashboard-loading">Reading the running community…</Card>;
  if (data?.status === "not_started") return <Card className="p-4" data-testid="dashboard-not-started">No simulated community run exists yet.</Card>;
  if (!data) return <Card className="p-4"><ReadState error={error} stale={false} /></Card>;

  const trail = stack.map((v) => titleCase(v.kind)).join(" › ");
  if (view) {
    const props = { id: view.id, runId: data.run.run_id, onOpenRequest, onChanged: reload, ...nav };
    return (
      <Card className="space-y-4 p-4 sm:p-5" data-testid="live-dashboard">
        <BackBar trail={`Dashboard › ${trail}`} onBack={back} />
        {view.kind === "department" && <DashboardDepartment {...props} />}
        {view.kind === "worker" && <DashboardWorker {...props} />}
        {view.kind === "resident" && <DashboardResident {...props} />}
        {view.kind === "ticket" && <DashboardTicket {...props} />}
        {view.kind === "residents" && <Section title="Residents" count={data.residents.length}><PeopleList rows={data.residents} kind="residents" onOpen={nav.onResident} /></Section>}
        {view.kind === "staff" && <Section title="Staff" count={data.staff.length}><PeopleList rows={data.staff} kind="staff" onOpen={nav.onWorker} /></Section>}
      </Card>
    );
  }

  const c = data.counts;
  return (
    <Card className="space-y-5 p-4 sm:p-5" data-testid="live-dashboard">
      <ReadState error={error} stale={stale} />
      <Header run={data.run} pace={pace} />
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-4 lg:grid-cols-7">
        <Stat label="Staff on duty" value={c.workers_on_duty} onClick={() => open("staff")} testId="stat-staff" />
        <Stat label="Residents" value={c.residents} onClick={() => open("residents")} testId="stat-residents" />
        <Stat label="Waiting" value={c.pending} testId="stat-waiting" />
        <Stat label="In progress" value={c.in_progress} testId="stat-in-progress" />
        <Stat label="Completed" value={c.completed} testId="stat-completed" />
        <Stat label="Overdue" value={c.overdue} tone={c.overdue ? "text-caos-terracotta" : undefined} testId="stat-overdue" />
        <Stat label="On call" value={c.workers_on_call} testId="stat-on-call" />
      </div>
      <p className="text-xs text-caos-mute">Open a department to see its waiting, active and completed work. Staff and Residents open their lists.</p>
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4" data-testid="dashboard-departments">
        {data.departments.map((dept) => <DepartmentBox key={dept.slug} dept={dept} onOpen={nav.onDepartment} />)}
      </div>
      <p className="text-xs text-caos-mute">{data.truth}</p>
    </Card>
  );
}
