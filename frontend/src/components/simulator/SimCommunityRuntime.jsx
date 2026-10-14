import React from "react";
import { Badge } from "../ui/badge";
import { Button } from "../ui/button";
import { Card } from "../ui/card";
import { Progress } from "../ui/progress";
import SimCommunityActivity from "./SimCommunityActivity";

const STATE_CLASS = {
  RUNNING: "border-caos-moss bg-caos-moss/20 text-caos-forest",
  PAUSED: "border-caos-amber bg-caos-amber/20 text-[#8B5A20]",
  STOPPED: "border-caos-line bg-caos-mute/10 text-caos-mute",
};

const titleCase = (value) => String(value || "unknown").replaceAll("_", " ");
const shown = (value) => (value === null || value === undefined ? "Unknown" : value);

function SourceStatus({ label, status }) {
  const className = status === "loaded"
    ? "text-caos-forest"
    : status === "error"
      ? "text-caos-terracotta"
      : "text-caos-mute";
  return (
    <Badge variant="outline" className={className}>
      {label}: {titleCase(status)}
    </Badge>
  );
}

function TicketCounts({ tickets }) {
  const rows = [
    ["Opened", tickets?.counts?.open],
    ["In progress", tickets?.counts?.in_progress],
    ["Completed", tickets?.counts?.completed],
  ];
  return (
    <section aria-labelledby="runtime-tickets-heading">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 id="runtime-tickets-heading" className="text-xs font-bold uppercase tracking-widest text-caos-mute">
          Canonical tickets
        </h3>
        <SourceStatus label="Ticket read" status={tickets?.status} />
      </div>
      <dl className="mt-2 grid grid-cols-3 gap-2" data-testid="runtime-ticket-counts">
        {rows.map(([label, value]) => (
          <div key={label} className="rounded-lg border border-caos-line bg-white p-3">
            <dt className="text-xs text-caos-mute">{label}</dt>
            <dd className={`mt-1 font-display text-2xl ${value == null ? "text-caos-mute" : "text-caos-forest"}`}>
              {shown(value)}
            </dd>
          </div>
        ))}
      </dl>
    </section>
  );
}

function NextEvent({ event }) {
  if (!event) return <p className="mt-1 text-sm italic text-caos-mute">No next event was reported.</p>;
  return (
    <div className="mt-1 text-sm" data-testid="runtime-next-event">
      <p className="font-semibold text-caos-forest">{titleCase(event.action_type)}</p>
      <p className="text-caos-mute">
        {event.actor_name || event.actor_id || "Actor unknown"}
        {event.department ? ` · ${titleCase(event.department)}` : ""}
        {event.blocked ? " · blocked" : ""}
      </p>
      <p className="font-mono text-xs text-caos-mute">{event.event_id}</p>
    </div>
  );
}

function LastEvidence({ receipt }) {
  if (!receipt) return <p className="mt-1 text-sm italic text-caos-mute">No execution receipt was reported.</p>;
  return (
    <div className="mt-1 text-sm" data-testid="runtime-last-receipt">
      <p className="font-semibold text-caos-forest">{titleCase(receipt.action_type)} · {titleCase(receipt.status)}</p>
      <p className="text-caos-mute">
        {receipt.actor_name || receipt.actor_id || "Actor unknown"}
        {receipt.actor_department ? ` · ${titleCase(receipt.actor_department)}` : ""}
      </p>
      <p className="font-mono text-xs text-caos-mute">{receipt.receipt_id}</p>
    </div>
  );
}

const DEPARTMENT_STATUS = {
  on_duty: (coverage) => `On duty · ${coverage.on_shift} on site`,
  on_call: (coverage) => `On call · ${coverage.on_call} off site`,
  closed: () => "Closed",
  uncovered: () => "UNCOVERED",
  simulation_complete: () => "Simulation complete",
};

// Older snapshots carry only on_shift; never call a closed department a gap.
function departmentStatus(coverage) {
  if (coverage.status) return coverage.status;
  if (coverage.on_shift == null) return null;
  return coverage.on_shift > 0 ? "on_duty" : "uncovered";
}

function StaffingCoverage({ staffing }) {
  const rows = staffing?.coverage ? Object.entries(staffing.coverage) : [];
  return (
    <section aria-labelledby="runtime-coverage-heading">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 id="runtime-coverage-heading" className="text-xs font-bold uppercase tracking-widest text-caos-mute">
          Departments now
        </h3>
        <SourceStatus label="Staffing read" status={staffing?.status} />
      </div>
      {!rows.length ? (
        <p className="mt-2 text-sm italic text-caos-mute">Coverage is unknown; no department totals were reported.</p>
      ) : (
        <ul className="mt-2 grid gap-2 sm:grid-cols-2 xl:grid-cols-4" data-testid="runtime-coverage">
          {rows.map(([department, coverage]) => {
            const status = departmentStatus(coverage);
            const describe = DEPARTMENT_STATUS[status];
            return (
              <li key={department} className="rounded-lg border border-caos-line bg-white p-3" data-status={status || "unknown"}>
                <p className="text-sm font-semibold text-caos-forest">{coverage.label || titleCase(department)}</p>
                <p className={status === "uncovered" ? "text-sm font-semibold text-caos-terracotta" : "text-sm text-caos-mute"}>
                  {describe ? describe(coverage) : "Coverage unknown"}
                </p>
                {coverage.operating_hours && (
                  <p className="text-xs text-caos-mute">Hours {coverage.operating_hours}</p>
                )}
              </li>
            );
          })}
        </ul>
      )}
      {staffing?.gaps?.length > 0 && (
        <p className="mt-2 text-sm font-semibold text-caos-terracotta" data-testid="runtime-coverage-gaps">
          Uncovered now: {staffing.gaps.map(titleCase).join(", ")}
        </p>
      )}
    </section>
  );
}

export default function SimCommunityRuntime({ loadState, snapshot, refreshFailed = false, onRetry, onOpenRequest }) {
  if (loadState === "loading" && !snapshot) {
    return (
      <Card className="border-caos-line p-4" data-testid="community-runtime-loading">
        <h2 className="font-display text-xl text-caos-forest">Community runtime</h2>
        <p className="mt-1 text-sm text-caos-mute">Reading the execution engine and canonical ticket state…</p>
      </Card>
    );
  }

  if (!snapshot) {
    return (
      <Card className="border-caos-line p-4" data-testid="community-runtime-error">
        <h2 className="font-display text-xl text-caos-forest">Community runtime unknown</h2>
        <p className="mt-1 text-sm text-caos-mute">
          The read-only runtime endpoint did not answer. This is not evidence that the engine is running, stopped,
          or that there are zero tickets.
        </p>
        <Button type="button" variant="outline" className="mt-3" onClick={onRetry}>Retry runtime read</Button>
      </Card>
    );
  }

  const run = snapshot.run;
  const state = run.state;
  const clock = run.simulated_time || {};
  const progress = run.progress || {};
  const noRun = run.status === "not_started";

  return (
    <Card className="border-caos-line p-4 sm:p-5 space-y-5" data-testid="community-runtime-ready">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="font-display text-2xl text-caos-forest">Community runtime</h2>
          <p className="mt-1 text-sm text-caos-mute">{snapshot.truth_statement || "Read-only execution truth from canonical records."}</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Badge variant="outline" className="border-caos-line text-caos-mute">READ ONLY</Badge>
          <Badge variant="outline" className={state ? STATE_CLASS[state] : "border-caos-line text-caos-mute"} data-testid="runtime-state">
            {state || (noRun ? "NOT STARTED" : "UNKNOWN")}
          </Badge>
        </div>
      </header>

      <p className="text-sm text-caos-mute" data-testid="runtime-motion-status" aria-live="polite">
        {state === "RUNNING"
          ? "Live: the simulated clock, canonical tickets, and receipt-backed changes refresh every two seconds."
          : state === "PAUSED"
            ? "Paused: the simulated clock and autonomous work stay fixed until resume; real human actions can still appear."
            : state === "STOPPED"
              ? "Stopped: no new simulator actions run; ticket history and receipts remain available."
              : "Runtime movement is unknown until an exact run state is available."}
      </p>

      {refreshFailed && (
        <div className="rounded-lg border border-caos-amber bg-[#FDF3E3] p-3 text-sm" data-testid="community-runtime-stale">
          Live refresh failed. Showing the last received read from {snapshot.generated_at}; unknown values were not replaced with zero.
        </div>
      )}
      {snapshot.status !== "loaded" && !refreshFailed && (
        <div className="rounded-lg border border-caos-amber bg-[#FDF3E3] p-3 text-sm" data-testid="community-runtime-partial">
          Runtime truth is {snapshot.status}. Unavailable sources remain visibly unknown.
        </div>
      )}

      <section aria-labelledby="runtime-position-heading">
        <h3 id="runtime-position-heading" className="text-xs font-bold uppercase tracking-widest text-caos-mute">Execution position</h3>
        {noRun ? (
          <p className="mt-2 text-sm text-caos-mute">No living-community run has been started. The 90-day plan is not running.</p>
        ) : (
          <div className="mt-2 space-y-2">
            <div className="flex flex-wrap gap-x-5 gap-y-1 text-sm">
              <span>Time <b>{clock.day_index == null ? "Unknown" : `Day ${clock.day_index + 1} · ${clock.hh_mm || `minute ${clock.minute}`}`}</b></span>
              <span>Cursor <b>{shown(run.cursor)} of {shown(run.event_count)}</b></span>
              <span>Run <b className="font-mono text-xs">{run.run_id || "Unknown"}</b></span>
            </div>
            {progress.percent == null ? (
              <p className="text-xs text-caos-mute">Progress unknown.</p>
            ) : (
              <>
                <Progress value={progress.percent} aria-label="Runtime progress" aria-valuetext={`${progress.percent}% complete`} />
                <p className="text-xs text-caos-mute">{progress.completed_events} of {progress.total_events} events receipted · {progress.percent}%</p>
              </>
            )}
          </div>
        )}
      </section>

      <TicketCounts tickets={snapshot.tickets} />

      <div className="grid gap-4 lg:grid-cols-2">
        <section className="rounded-lg border border-caos-line p-3" aria-labelledby="runtime-next-heading">
          <h3 id="runtime-next-heading" className="text-xs font-bold uppercase tracking-widest text-caos-mute">Next planned action</h3>
          <NextEvent event={run.next_event} />
        </section>
        <section className="rounded-lg border border-caos-line p-3" aria-labelledby="runtime-receipt-heading">
          <h3 id="runtime-receipt-heading" className="text-xs font-bold uppercase tracking-widest text-caos-mute">Last execution receipt</h3>
          <LastEvidence receipt={run.last_evidence} />
        </section>
      </div>

      <StaffingCoverage staffing={snapshot.staffing} />
      <SimCommunityActivity activity={snapshot.activity} runId={run.run_id} onOpenRequest={onOpenRequest} />
      <div className="flex flex-wrap items-center justify-between gap-2 border-t border-caos-line pt-3">
        <div className="flex flex-wrap gap-2" aria-label="Runtime source status">
          {Object.entries(snapshot.sources || {}).map(([source, value]) => (
            <SourceStatus key={source} label={titleCase(source)} status={value?.status} />
          ))}
        </div>
        <Button type="button" variant="outline" onClick={onRetry}>Refresh runtime</Button>
      </div>
    </Card>
  );
}
