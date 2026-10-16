import React from "react";
import { Badge } from "../ui/badge";
import { Button } from "../ui/button";
import { minutes, simTime, STATUS_CLASS, STATUS_LABEL, titleCase } from "../../lib/dashboardFormat";

export function Stat({ label, value, tone, onClick, testId }) {
  const body = (
    <>
      <span className="block text-xs text-caos-mute">{label}</span>
      <span className={`mt-1 block font-display text-2xl ${tone || "text-caos-forest"}`}>{value ?? "—"}</span>
    </>
  );
  const cls = "rounded-lg border border-caos-line bg-white p-3 text-left";
  return onClick
    ? <button type="button" className={`${cls} hover:border-caos-moss`} onClick={onClick} data-testid={testId}>{body}</button>
    : <div className={cls} data-testid={testId}>{body}</div>;
}

export function Section({ title, count, children, testId }) {
  return (
    <section className="space-y-2" data-testid={testId}>
      <h3 className="text-sm font-semibold text-caos-forest">
        {title}{count !== undefined && <span className="ml-1 text-caos-mute">({count})</span>}
      </h3>
      {children}
    </section>
  );
}

export function Empty({ children }) {
  return <p className="text-sm text-caos-mute">{children}</p>;
}

export function StatusBadge({ status }) {
  return <Badge variant="outline" className={STATUS_CLASS[status] || ""}>{STATUS_LABEL[status] || titleCase(status)}</Badge>;
}

// One clickable ticket row: what, who, when, and how long it has waited.
export function TicketList({ rows, onTicket, empty = "None.", testId }) {
  if (!rows?.length) return <Empty>{empty}</Empty>;
  return (
    <ul className="divide-y divide-caos-line rounded-lg border border-caos-line bg-white" data-testid={testId}>
      {rows.map((row) => (
        <li key={row.task_id}>
          <button type="button" onClick={() => onTicket(row.task_id)} data-testid={`ticket-${row.task_id}`}
                  className="flex w-full flex-wrap items-start justify-between gap-2 p-3 text-left hover:bg-caos-mute/5">
            <span className="min-w-0">
              <span className="block text-sm font-semibold text-caos-forest">{row.what || titleCase(row.routine) || "Ticket"}</span>
              <span className="block text-xs text-caos-mute">
                {row.resident?.name || "Resident unknown"}{row.resident?.room ? ` · ${row.resident.room}` : ""}
                {" · requested "}{simTime(row.requested)}
                {row.worker?.name ? ` · ${row.worker.name}${row.worker.real_staff ? " (real staff)" : ""}` : ""}
              </span>
              {row.waiting_minutes !== null && row.waiting_minutes !== undefined && (
                <span className={`block text-xs ${row.overdue ? "font-semibold text-caos-terracotta" : "text-caos-mute"}`}>
                  Waiting {minutes(row.waiting_minutes)}{row.overdue ? " · overdue" : ""}
                </span>
              )}
            </span>
            <StatusBadge status={row.status} />
          </button>
        </li>
      ))}
    </ul>
  );
}

export function PlannedList({ rows, empty = "Nothing more planned today." }) {
  if (!rows?.length) return <Empty>{empty}</Empty>;
  return (
    <ul className="divide-y divide-caos-line rounded-lg border border-dashed border-caos-line bg-white">
      {rows.map((row, index) => (
        <li key={`${row.routine}-${row.at?.absolute_minute}-${row.resident_id}-${index}`} className="flex flex-wrap justify-between gap-2 p-2 text-sm">
          <span>{row.label || titleCase(row.routine)}{row.worker ? ` · ${row.worker}` : ""}</span>
          <span className="text-xs text-caos-mute">planned {simTime(row.at)}</span>
        </li>
      ))}
    </ul>
  );
}

export function BackBar({ trail, onBack }) {
  return (
    <div className="flex flex-wrap items-center gap-2 text-sm" data-testid="dashboard-backbar">
      <Button type="button" variant="outline" size="sm" onClick={onBack} data-testid="dashboard-back">Back</Button>
      <span className="text-caos-mute">{trail}</span>
    </div>
  );
}

export function ReadState({ error, stale }) {
  if (!error) return null;
  return (
    <p className="rounded-lg border border-caos-amber bg-[#FDF3E3] p-2 text-sm" data-testid="dashboard-read-error">
      {stale ? "Refresh failed; showing the last good read. " : "Could not read this view. "}{String(error)}
    </p>
  );
}
