import React, { useCallback, useEffect, useRef, useState } from "react";
import { api, API } from "../lib/api";
import { Card } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Badge } from "../components/ui/badge";
import { Download } from "lucide-react";
import { toast } from "sonner";
import RequestHistoryDialog from "./RequestHistoryDialog";
import { LOG_STATUSES, LOG_STATUS_LABEL, LOG_STATUS_TONE, logQuery, pickupLabel, latestOnly, csvFileName } from "../lib/rideLog";

function ymd(d) { return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`; }

export default function TransportLog() {
  const today = new Date(); const wk = new Date(); wk.setDate(wk.getDate() - 6);
  const [f, setF] = useState({ from: ymd(wk), to: ymd(today), status: "", q: "" });
  const [data, setData] = useState(null);
  const [hist, setHist] = useState(null);

  const seq = useRef(latestOnly());
  const load = useCallback(async () => {
    const mine = seq.current.next();   // only the newest request may update the screen (an older, slower reply must not overwrite it)
    try {
      const res = (await api.get(`/transportation/log?${logQuery(f)}`)).data;
      if (seq.current.isCurrent(mine)) setData(res);
    } catch (e) {
      if (seq.current.isCurrent(mine)) { setData(null); toast.error(e?.response?.data?.detail || "Could not load the ride log"); }
    }
  }, [f]);
  useEffect(() => { load(); }, [load]);
  useEffect(() => { const g = seq.current; return () => g.invalidate(); }, []);   // unmounted: a late reply or failure is dropped

  const csv = async () => {
    try {
      const res = await fetch(`${API}/transportation/log?${logQuery(f)}&format=csv`, { headers: { Authorization: `Bearer ${localStorage.getItem("caos_token")}` } });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const url = URL.createObjectURL(await res.blob());
      const a = document.createElement("a"); a.href = url; const partial = res.headers.get("X-Truncated") === "true";
      a.download = csvFileName(f, partial);
      if (partial) toast.warning("This export is PARTIAL: more rides matched than the export limit. Narrow the date range and export again.");
      document.body.appendChild(a); a.click(); document.body.removeChild(a); URL.revokeObjectURL(url);
    } catch (e) { toast.error(e?.message || "Download failed"); }
  };

  return (
    <Card className="border-caos-line p-4 sm:p-6" data-testid="transport-log-root">
      <h2 className="font-display text-xl font-medium text-caos-forest">Ride log</h2>
      <p className="text-caos-mute text-sm mt-1 mb-4">Rides in the range, any outcome: who asked, who drove, what happened. Click a row for its full history. If the list is cut off, it says so.</p>
      <div className="flex flex-wrap gap-2 items-center mb-3">
        <Input type="date" value={f.from} onChange={(e) => setF({ ...f, from: e.target.value })} className="w-auto" data-testid="log-from" />
        <Input type="date" value={f.to} onChange={(e) => setF({ ...f, to: e.target.value })} className="w-auto" data-testid="log-to" />
        <select value={f.status} onChange={(e) => setF({ ...f, status: e.target.value })} className="border rounded-md h-9 px-2 text-sm" data-testid="log-status">
          <option value="">All outcomes</option>
          {LOG_STATUSES.map((s) => <option key={s} value={s}>{LOG_STATUS_LABEL[s]}</option>)}
        </select>
        <Input placeholder="Search resident, room, driver" value={f.q} onChange={(e) => setF({ ...f, q: e.target.value })} className="w-56 max-w-full" data-testid="log-q" />
        <Button variant="outline" className="border-2 rounded-full" onClick={csv} data-testid="log-csv"><Download className="w-4 h-4 mr-1" /> CSV</Button>
      </div>
      {data && (
        <div className="flex flex-wrap gap-2 mb-3 text-xs" data-testid="log-counts">
          <Badge variant="outline">{data.total} rides</Badge>
          {LOG_STATUSES.map((s) => <Badge key={s} className={LOG_STATUS_TONE[s]}>{LOG_STATUS_LABEL[s]} {data.counts[s]}</Badge>)}
        </div>
      )}
      {data?.truncated && <p className="text-sm text-caos-terracotta mb-2" data-testid="log-truncated">{data.truncated_note}</p>}
      {data && data.rows.length === 0 && <p className="text-caos-mute text-sm">No rides in this range.</p>}
      <div className="grid gap-2">
        {(data?.rows || []).map((r) => (
          <button key={r.task_id} onClick={() => setHist(r.task_id)} className="text-left border rounded-lg p-3 hover:bg-caos-bone/40" data-testid={`log-row-${r.task_id}`}>
            <div className="flex flex-wrap justify-between gap-2">
              <span className="font-medium">{r.resident_name || "Unknown"} <span className="text-caos-mute font-normal">· Room {r.room || "-"}</span></span>
              <Badge className={LOG_STATUS_TONE[r.status]}>{LOG_STATUS_LABEL[r.status]}</Badge>
            </div>
            <div className="text-sm text-caos-mute mt-1">
              {r.purpose || "-"} · appointment {r.appointment_date || "-"} {r.appointment_time || ""} · pickup {pickupLabel(r)}
            </div>
            <div className="text-xs text-caos-mute mt-1">
              Driver {r.driver || "-"} · {r.vehicle || "no vehicle"} · asked {r.times_asked}× via {r.source || "-"} · {r.receipt_count} receipts
              {r.last_note ? ` · "${r.last_note}"` : ""}
            </div>
          </button>
        ))}
      </div>
      <RequestHistoryDialog taskId={hist} onClose={() => setHist(null)} />
    </Card>
  );
}
