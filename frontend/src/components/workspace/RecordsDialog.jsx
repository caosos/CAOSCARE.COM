import { useEffect, useState } from "react";
import { Search } from "lucide-react";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "../ui/dialog";
import { api } from "../../lib/api";
import { fetchRecords, periodParams } from "../../lib/useWorkspaceData";
import RequestDetailDialog from "../../pages/RequestDetailDialog";
import DashboardWorker from "../dashboard/DashboardWorker";

const ORIGINS = [["scheduled_routine", "Scheduled routine"], ["resident_request", "Resident request"],
                 ["staff_generated", "Staff / system"], ["unknown", "Origin not recorded"]];

const when = (iso) => (iso ? new Date(iso).toLocaleString([], { month: "short", day: "numeric",
  hour: "numeric", minute: "2-digit" }) : "—");

function WorldBadge({ world }) {
  const sim = world === "simulated";
  return (
    <span className={`rounded-full px-2.5 py-0.5 text-xs font-semibold ${sim ? "bg-[#EDE9FE] text-[#5B21B6]" : "bg-[#DCFCE7] text-[#166534]"}`}>
      {sim ? "SIMULATED" : "LIVE"}
    </span>
  );
}

// What a box's number is, and every record behind it.
const ACTOR = { real: "real person", simulated: "simulated worker", none: "not claimed" };

// What a number covers: facility, world/run, period, timezone, status, origin (#153 slice 2).
function Disclosure({ data, origin }) {
  const facts = [
    ["Facility", data.facility ? (data.facility.name || "—") + (data.facility.basis ? ` (${data.facility.basis})` : "") : null],
    ["World", data.world === "simulated" ? `Simulated run ${data.run?.run_id || "?"}` : "Live records only (simulated excluded)"],
    ["Period", data.period?.kind === "sim_day" ? `${data.period.label} (simulated day, not a wall date)` : `${data.period?.label || "—"} (real wall date)`],
    ["Timezone", data.timezone],
    ["Status", data.status_filter?.length ? data.status_filter.join(" or ") : "any"],
    ["Origin", origin || "all origins"],
  ].filter(([, v]) => v);
  return (
    <dl className="grid grid-cols-1 gap-x-4 gap-y-1 rounded-lg bg-[#F9FAFB] p-3 text-[13px] sm:grid-cols-2" data-testid="ws-disclosure">
      {facts.map(([k, v]) => (
        <div key={k} className="flex gap-2"><dt className="font-semibold text-[#374151]">{k}</dt><dd className="text-[#4B5563]">{v}</dd></div>
      ))}
    </dl>
  );
}

export default function RecordsDialog({ widget, view, open, onOpenChange, expectedTotal }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [page, setPage] = useState(1);
  const [q, setQ] = useState("");
  const [origin, setOrigin] = useState(undefined);
  const [counts, setCounts] = useState({});
  const [taskId, setTaskId] = useState(null);
  const [workerId, setWorkerId] = useState(null);
  const isMetric = widget?.source.kind === "metric";
  const fixedOrigin = widget?.source.origin;

  useEffect(() => { setPage(1); setQ(""); setOrigin(undefined); setData(null); }, [widget, view]);

  useEffect(() => {
    if (!open || !widget) return;
    let live = true;
    fetchRecords(widget, view, { page, q, origin })
      .then((d) => { if (live) { setData(d); setError(null); } })
      .catch((e) => live && setError(e?.response?.data?.detail || "Could not load the records"));
    return () => { live = false; };
  }, [open, widget, view, page, q, origin]);

  useEffect(() => {
    if (!open || !isMetric || fixedOrigin) return;
    const src = widget.source;
    Promise.all(ORIGINS.map(([k]) => api.get("/ops/metrics/records", { params: { ...periodParams(view),
      metric: src.metric, department: src.department, origin: k, page_size: 1 } })
      .then(({ data: d }) => [k, d.total]).catch(() => [k, null])))
      .then((pairs) => setCounts(Object.fromEntries(pairs)));
  }, [open, widget, view, isMetric, fixedOrigin]);

  const rows = data?.rows || [];
  const pages = data?.kind === "tasks" ? Math.max(1, Math.ceil((data.matched ?? data.total) / data.page_size)) : 1;
  return (
    <>
      <Dialog open={open} onOpenChange={onOpenChange}>
        <DialogContent className="max-h-[90vh] max-w-4xl overflow-y-auto" data-testid="ws-records">
          <DialogHeader>
            <DialogTitle className="flex flex-wrap items-center gap-2 text-xl">
              {widget?.title} — {widget?.subtitle}
              {data && <WorldBadge world={data.world} />}
            </DialogTitle>
            <DialogDescription asChild>
              <div className="space-y-1 text-[14px] text-[#374151]">
                {data && <p><span className="font-semibold">{data.value ?? data.total}</span> · {data.period?.label}</p>}
                {data?.explanation && <p data-testid="ws-explanation">{data.explanation}</p>}
                {data?.unverified && <p className="text-[#B42318]">{data.unverified}</p>}
                {data?.kind === "tasks" && expectedTotal != null && origin === undefined && !q && data.total !== expectedTotal && (
                  <p className="font-semibold text-[#B42318]" data-testid="ws-unverified">
                    UNVERIFIED: the box showed {expectedTotal} but {data.total} records match now — the records changed
                    after the box loaded. Refresh to see a matching pair.
                  </p>
                )}
                {data?.run?.clock && (
                  <p className="text-[#6B7280]">Run clock: day {data.run.clock.day}, {data.run.clock.hh_mm}
                    {data.run.executed_through_day ? ` · records reflect day ${data.run.executed_through_day}` : ""}</p>
                )}
              </div>
            </DialogDescription>
          </DialogHeader>
          {data?.kind === "tasks" && <Disclosure data={data} origin={origin ?? fixedOrigin} />}
          {isMetric && !fixedOrigin && (
            <div className="flex flex-wrap gap-2">
              <button type="button" onClick={() => { setOrigin(undefined); setPage(1); }}
                      className={`rounded-full border px-3 py-1 text-sm ${!origin ? "border-[#111827] bg-[#111827] text-white" : "border-[#E5E7EB] bg-white"}`}>
                All {data && origin === undefined ? `(${data.total})` : ""}
              </button>
              {ORIGINS.map(([k, label]) => (
                <button key={k} type="button" onClick={() => { setOrigin(k); setPage(1); }}
                        className={`rounded-full border px-3 py-1 text-sm ${origin === k ? "border-[#111827] bg-[#111827] text-white" : "border-[#E5E7EB] bg-white"}`}>
                  {label} {counts[k] != null ? `(${counts[k]})` : ""}
                </button>
              ))}
            </div>
          )}
          {data?.kind === "tasks" && (
            <label className="flex items-center gap-2 rounded-lg border border-[#E5E7EB] px-3 py-2">
              <Search className="h-4 w-4 text-[#9CA3AF]" />
              <input value={q} onChange={(e) => { setQ(e.target.value); setPage(1); }} placeholder="Search resident, room, worker, task…"
                     className="w-full bg-transparent text-sm outline-none" aria-label="Search records" />
            </label>
          )}
          {error && <p className="text-sm text-[#B42318]">{error}</p>}
          {data?.kind === "tasks" && (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-[13px]">
                <thead className="text-[#6B7280]">
                  <tr><th className="py-2 pr-3">Task</th><th className="pr-3">Task ID · receipts</th><th className="pr-3">Origin</th><th className="pr-3">Resident</th>
                    <th className="pr-3">Worker</th><th className="pr-3">Status</th><th className="pr-3">Created</th><th>Finished</th></tr>
                </thead>
                <tbody>
                  {rows.map((r) => (
                    <tr key={r.task_id} onClick={() => setTaskId(r.task_id)} data-testid="ws-record-row"
                        className="cursor-pointer border-t border-[#F3F4F6] hover:bg-[#F9FAFB]">
                      <td className="py-2 pr-3"><div className="font-medium text-[#111827]">{r.summary}</div>
                        <div className="text-[#9CA3AF]">{r.department}{r.routine ? ` · ${r.routine.replace(/_/g, " ")}` : ""}</div></td>
                      <td className="pr-3">
                        {/* A real button: Tab + Enter opens this task's detail with its receipts. */}
                        <button type="button" data-testid="ws-record-open" aria-label={`Open task ${r.task_id} and its receipts`}
                                onClick={(e) => { e.stopPropagation(); setTaskId(r.task_id); }}
                                className="rounded font-mono text-[12px] text-[#1D4ED8] underline focus:outline-none focus-visible:ring-2 focus-visible:ring-[#1D72D8]">
                          {r.task_id}
                        </button>
                      </td>
                      <td className="pr-3">{r.origin_label}{r.world === "simulated" ? " · sim" : ""}</td>
                      <td className="pr-3">{r.resident_name || "—"}{r.room ? ` · ${r.room}` : ""}</td>
                      <td className="pr-3">{r.worker || "—"}{r.actor_kind ? <div className="text-[#9CA3AF]">{ACTOR[r.actor_kind] || r.actor_kind}</div> : null}</td>
                      <td className="pr-3">{r.status}</td>
                      <td className="pr-3">{when(r.created_at)}</td>
                      <td>{when(r.completed_at)}</td>
                    </tr>
                  ))}
                  {!rows.length && <tr><td colSpan={8} className="py-6 text-center text-[#6B7280]">No records match.</td></tr>}
                </tbody>
              </table>
              <div className="mt-3 flex items-center justify-between text-sm text-[#4B5563]">
                <span>{q ? `${data.matched} of ${data.total} match` : `${data.total} records`} · page {data.page} of {pages}</span>
                <span className="space-x-2">
                  <button type="button" disabled={page <= 1} onClick={() => setPage((p) => p - 1)} className="rounded border px-3 py-1 disabled:opacity-40">Previous</button>
                  <button type="button" disabled={page >= pages} onClick={() => setPage((p) => p + 1)} className="rounded border px-3 py-1 disabled:opacity-40">Next</button>
                </span>
              </div>
            </div>
          )}
          {data?.kind === "list" && (
            <ul className="divide-y divide-[#F3F4F6] text-[14px]">
              {rows.map((r) => (
                <li key={r.id} className={`py-2 ${r.task_id ? "cursor-pointer hover:bg-[#F9FAFB]" : ""}`}
                    onClick={() => r.task_id && setTaskId(r.task_id)}>
                  {r.worker_id ? (
                    // A worker opens their own detail; a real button, so it works from the keyboard.
                    <button type="button" onClick={() => setWorkerId(r.worker_id)} data-testid="ws-worker-row"
                            className="w-full rounded text-left hover:bg-[#F9FAFB] focus:outline-none focus-visible:ring-2 focus-visible:ring-[#1D72D8]">
                      <span className="font-medium text-[#111827] underline-offset-2 hover:underline">{r.name}</span>
                      <span className="text-[#6B7280]"> · {r.detail}</span>
                    </button>
                  ) : (
                    <>
                      <span className="font-medium text-[#111827]">{r.name}</span>
                      <span className="text-[#6B7280]"> · {r.detail}</span>
                    </>
                  )}
                </li>
              ))}
              {!rows.length && <li className="py-6 text-center text-[#6B7280]">No records.</li>}
            </ul>
          )}
        </DialogContent>
      </Dialog>
      <Dialog open={!!workerId} onOpenChange={(o) => !o && setWorkerId(null)}>
        <DialogContent className="max-h-[90vh] max-w-3xl overflow-y-auto" data-testid="ws-worker-detail">
          <DialogHeader><DialogTitle className="sr-only">Worker detail</DialogTitle></DialogHeader>
          {workerId && <DashboardWorker id={workerId} runId={data?.run?.run_id} onTicket={setTaskId} />}
        </DialogContent>
      </Dialog>
      <RequestDetailDialog taskId={taskId} open={!!taskId} onOpenChange={(o) => !o && setTaskId(null)} />
    </>
  );
}
