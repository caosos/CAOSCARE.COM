import React from "react";
import { Button } from "../ui/button";
import useDashboardResource from "../../lib/useDashboardResource";
import { minutes, simTime, titleCase } from "../../lib/dashboardFormat";
import { ReadState, Section, StatusBadge } from "./DashboardParts";

function Fact({ label, children }) {
  return (
    <div className="rounded-lg border border-caos-line bg-white p-2">
      <dt className="text-xs text-caos-mute">{label}</dt>
      <dd className="text-sm text-caos-forest">{children}</dd>
    </div>
  );
}

function Receipts({ rows }) {
  return (
    <ol className="space-y-1" data-testid="ticket-receipts">
      {rows.map((r) => (
        <li key={r.receipt_id} className="rounded border border-caos-line bg-white p-2 text-sm">
          <span className="font-semibold text-caos-forest">{titleCase(r.action)}</span>
          {r.before || r.after ? ` · ${titleCase(r.before) || "new"} → ${titleCase(r.after)}` : ""}
          <span className="block text-xs text-caos-mute">
            {r.actor.name || r.actor.id || "actor unknown"} ({titleCase(r.actor.type)}) · {r.source}
            {r.simulated_at ? ` · simulated ${simTime(r.simulated_at)}` : ""} · status {r.status}
          </span>
          {r.result && <span className="block text-xs">{r.result}</span>}
          <span className="block font-mono text-[11px] text-caos-mute">{r.receipt_id}{r.parent_receipt_id ? ` ← ${r.parent_receipt_id}` : ""}</span>
        </li>
      ))}
    </ol>
  );
}

export default function DashboardTicket({ id, onOpenRequest, onResident, onWorker }) {
  const { data, error, stale } = useDashboardResource(`/simulator/community/dashboard/tickets/${encodeURIComponent(id)}`, 5000);
  if (!data) return error ? <ReadState error={error} /> : <p className="text-sm text-caos-mute">Loading ticket…</p>;
  const t = data.ticket;
  const tl = data.timeline;
  const simWorker = t.worker?.id?.startsWith("sim:staff:");
  return (
    <div className="space-y-5" data-testid="ticket-detail">
      <ReadState error={error} stale={stale} />
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="font-display text-2xl text-caos-forest">{t.what || titleCase(t.routine)}</h2>
          <p className="text-sm text-caos-mute">{titleCase(t.department)} · {titleCase(t.priority)} priority</p>
        </div>
        <span className="flex items-center gap-2">
          <StatusBadge status={t.status} />
          {onOpenRequest && <Button type="button" size="sm" variant="outline" onClick={() => onOpenRequest(t.task_id)} data-testid="ticket-open-actions">Open ticket actions</Button>}
        </span>
      </div>
      <dl className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4" data-testid="ticket-facts">
        <Fact label="Requested by">
          {t.requested_by?.id ? <button type="button" className="underline" onClick={() => onResident(t.requested_by.id)}>{t.requested_by.name}</button> : "Unknown"}
          {t.requested_by?.room ? ` · ${t.requested_by.room}` : ""}
        </Fact>
        <Fact label="Requested">{simTime(tl.requested)} (simulated)</Fact>
        <Fact label="Worker">
          {t.worker?.name ? (simWorker
            ? <button type="button" className="underline" onClick={() => onWorker(t.worker.id)}>{t.worker.name}</button>
            : `${t.worker.name} (real staff)`) : "Not yet assigned"}
        </Fact>
        <Fact label="Department">{titleCase(t.department)}</Fact>
        <Fact label="Started">{tl.started_real || simTime(tl.started)}</Fact>
        <Fact label="Finished">{tl.finished_real || simTime(tl.finished)}</Fact>
        <Fact label={tl.started || tl.started_real ? "Waited" : "Waiting so far"}>
          {minutes(tl.wait_minutes ?? t.waiting_minutes)}{tl.wait_reason && tl.wait_reason !== "none" ? ` · ${titleCase(tl.wait_reason)}` : ""}
        </Fact>
        <Fact label={`Work time (${tl.basis})`}>{minutes(tl.work_minutes)}</Fact>
      </dl>
      <p className="rounded-lg border border-caos-line bg-white p-3 text-sm" data-testid="ticket-outcome"><b>Outcome:</b> {data.outcome}</p>
      <Section title="Receipts" count={data.receipts.length}><Receipts rows={data.receipts} /></Section>
      <Section title="Action history" count={data.history.length}>
        <ul className="space-y-1 text-sm">
          {data.history.map((h, i) => (
            <li key={`${h.at}-${i}`}>{titleCase(h.field)}: {titleCase(h.from) || "—"} → {titleCase(h.to)} · {h.by_name || h.by} <span className="text-xs text-caos-mute">({h.at})</span></li>
          ))}
        </ul>
      </Section>
    </div>
  );
}
