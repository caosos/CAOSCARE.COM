import React from "react";
import { Badge } from "../ui/badge";
import { Button } from "../ui/button";

const titleCase = (value) => String(value || "unknown").replaceAll("_", " ");
const shown = (value) => (value === null || value === undefined ? "Unknown" : value);
const duration = (minutes) => {
  if (minutes === null || minutes === undefined) return "wait unknown";
  const hours = Math.floor(minutes / 60);
  return hours ? `${hours} h ${minutes % 60} min` : `${minutes} min`;
};
const STATUS = { on_duty: "On duty", on_call: "On call", closed: "Closed", uncovered: "UNCOVERED", simulation_complete: "Complete" };

function Totals({ totals }) {
  const rows = [
    ["Waiting", totals?.queued],
    ["Overdue", totals?.overdue],
    ["In progress", totals?.in_progress],
    ["Longest wait", totals?.longest_wait_minutes == null ? null : duration(totals.longest_wait_minutes)],
  ];
  return (
    <dl className="mt-2 grid grid-cols-2 gap-2 sm:grid-cols-4" data-testid="queue-totals">
      {rows.map(([label, value]) => (
        <div key={label} className="rounded-lg border border-caos-line bg-white p-3">
          <dt className="text-xs text-caos-mute">{label}</dt>
          <dd className="mt-1 font-display text-xl text-caos-forest">{shown(value)}</dd>
        </div>
      ))}
    </dl>
  );
}

function Departments({ departments }) {
  return (
    <div className="mt-3 overflow-x-auto">
      <table className="w-full min-w-[34rem] text-left text-sm" data-testid="queue-departments">
        <thead className="text-xs uppercase tracking-wide text-caos-mute">
          <tr><th className="py-1">Department</th><th>Status</th><th>Waiting</th><th>Overdue</th><th>Longest</th><th>Busy / free</th><th>On call</th></tr>
        </thead>
        <tbody>
          {Object.entries(departments).map(([key, row]) => (
            <tr key={key} className="border-t border-caos-line" data-status={row.status || "unknown"}>
              <td className="py-1 font-semibold text-caos-forest">{row.label}</td>
              <td className={row.status === "uncovered" ? "font-semibold text-caos-terracotta" : "text-caos-mute"}>{STATUS[row.status] || "Unknown"}</td>
              <td>{row.queued}</td>
              <td className={row.overdue ? "font-semibold text-caos-terracotta" : ""}>{row.overdue}</td>
              <td>{row.longest_wait_minutes == null ? "—" : duration(row.longest_wait_minutes)}</td>
              <td>{row.busy} / {row.free}</td>
              <td>{shown(row.on_call)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function QueuedTicket({ row, onOpenRequest }) {
  return (
    <li className="flex flex-wrap items-center justify-between gap-2 border-b border-caos-line py-2 last:border-0" data-testid={`queued-${row.task_id}`}>
      <div className="min-w-0">
        <p className="text-sm font-semibold text-caos-forest">{titleCase(row.department)} · {row.summary || "Summary unavailable"}</p>
        <p className={row.overdue ? "text-xs font-semibold text-caos-terracotta" : "text-xs text-caos-mute"}>
          Waiting {duration(row.waiting_minutes)}{row.overdue ? " · overdue" : ""} · {titleCase(row.priority)} priority
        </p>
        <p className="font-mono text-[11px] text-caos-mute">{row.task_id}</p>
      </div>
      {row.task_id && onOpenRequest && (
        <Button type="button" size="sm" variant="outline" onClick={() => onOpenRequest(row.task_id)}>Open ticket</Button>
      )}
    </li>
  );
}

function Worker({ row, onOpenRequest }) {
  const busy = row.availability === "busy";
  return (
    <li className="flex flex-wrap items-center justify-between gap-2 border-b border-caos-line py-1 last:border-0" data-testid={`worker-${row.actor_id}`}>
      <span className="text-sm">
        <b className="text-caos-forest">{row.name}</b>
        <span className="text-xs text-caos-mute"> · {titleCase(row.department)} · {titleCase(row.job_role)}</span>
      </span>
      <span className="flex items-center gap-2">
        <Badge variant="outline" className={busy ? "text-[#8B5A20]" : "text-caos-forest"}>{busy ? "Busy" : "Free"}</Badge>
        {busy && row.task_id && onOpenRequest && (
          <Button type="button" size="sm" variant="ghost" onClick={() => onOpenRequest(row.task_id)}>Ticket</Button>
        )}
      </span>
    </li>
  );
}

export default function SimCommunityQueue({ queue, runId, onOpenRequest }) {
  const exact = queue?.status === "loaded" && queue.run_id === runId;
  return (
    <section className="space-y-2 border-t border-caos-line pt-4" aria-labelledby="community-queue-heading">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h3 id="community-queue-heading" className="text-xs font-bold uppercase tracking-widest text-caos-mute">Work queue and capacity</h3>
          <p className="mt-1 text-xs text-caos-mute">
            One active ticket per on-site worker; everything else waits here. Waits are simulated minutes since the request
            {exact ? `; overdue means claimable for more than ${queue.overdue_after_minutes} min.` : "."}
          </p>
        </div>
        <Badge variant="outline" className={exact ? "text-caos-forest" : "text-caos-terracotta"}>{exact ? "loaded" : titleCase(queue?.status)}</Badge>
      </div>
      {!exact ? (
        <p className="text-sm italic text-caos-mute" data-testid="queue-unknown">The queue is unknown. This is not evidence that nothing is waiting.</p>
      ) : (
        <>
          {queue.executor_behind_clock_minutes > 0 && (
            <div className="rounded-lg border border-caos-amber bg-[#FDF3E3] p-3 text-sm" data-testid="queue-executor-lag">
              The executor is {duration(queue.executor_behind_clock_minutes)} behind the simulated clock. The queue is shown as of
              the last executed moment, so this lag is not counted as resident waiting time.
            </div>
          )}
          {queue.anomalies?.length > 0 && (
            <div className="rounded-lg border border-caos-terracotta p-3 text-sm font-semibold text-caos-terracotta" data-testid="queue-anomalies">
              Capacity rule broken: {queue.anomalies.map((row) => `${titleCase(row.kind)} (${row.actor_id})`).join("; ")}
            </div>
          )}
          <Totals totals={queue.totals} />
          <Departments departments={queue.departments} />
          <div className="grid gap-4 xl:grid-cols-2">
            <div>
              <h4 className="text-sm font-semibold text-caos-forest">Waiting longest ({queue.queued_shown} of {queue.totals.queued})</h4>
              {queue.queued.length === 0 ? <p className="mt-2 text-sm text-caos-mute">No ticket is waiting.</p> : (
                <ul className="mt-2 max-h-[28rem] overflow-y-auto rounded-lg border border-caos-line px-3" data-testid="queue-tickets">
                  {queue.queued.map((row) => <QueuedTicket key={row.task_id} row={row} onOpenRequest={onOpenRequest} />)}
                </ul>
              )}
            </div>
            <div>
              <h4 className="text-sm font-semibold text-caos-forest">On-site workers ({queue.workers.length})</h4>
              {queue.workers.length === 0 ? <p className="mt-2 text-sm text-caos-mute">No simulated worker is on site.</p> : (
                <ul className="mt-2 max-h-[28rem] overflow-y-auto rounded-lg border border-caos-line px-3" data-testid="queue-workers">
                  {queue.workers.map((row) => <Worker key={row.actor_id} row={row} onOpenRequest={onOpenRequest} />)}
                </ul>
              )}
            </div>
          </div>
        </>
      )}
    </section>
  );
}
