import React, { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../lib/api";
import { Card } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Badge } from "../components/ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "../components/ui/dialog";
import { toast } from "sonner";
import { humanizeAction, receiptStatusTone, receiptLink } from "../lib/activityLog";

const TONE_CLASS = {
  ok: "bg-caos-moss/15 text-caos-forest border border-caos-moss",
  info: "bg-caos-amber/15 text-[#8B5A20] border border-caos-amber",
  bad: "bg-caos-terracotta/15 text-caos-terracotta border border-caos-terracotta",
  muted: "bg-caos-mute/10 text-caos-mute",
};
const OBJECT_TYPES = ["", "task", "alert", "device_command"];
const STATUSES = ["", "created", "acknowledged", "in_progress", "completed", "failed", "cancelled"];

function fmt(iso) {
  if (!iso) return "—";
  try { return new Date(iso).toLocaleString(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" }); }
  catch { return iso; }
}

// Read-only browser over GET /receipts - the one operational-action log the
// dashboard/staff/Aria/audit systems already write to. No new endpoint.
export default function ReceiptsPanel({ onNavigate }) {
  const navigate = useNavigate();
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [f, setF] = useState({ object_type: "", status: "", since: "", until: "" });
  const [q, setQ] = useState("");
  const [selected, setSelected] = useState(null);

  const load = async () => {
    setLoading(true);
    try {
      const params = { limit: 500 };
      if (f.object_type) params.related_object_type = f.object_type;
      if (f.status) params.status = f.status;
      if (f.since) params.since = `${f.since}T00:00:00+00:00`;
      if (f.until) params.until = `${f.until}T23:59:59+00:00`;
      const { data } = await api.get("/receipts", { params });
      setRows(data);
    } catch {
      toast.error("Could not load receipts");
    } finally {
      setLoading(false);
    }
  };
  useEffect(() => { load(); }, [f.object_type, f.status, f.since, f.until]); // eslint-disable-line react-hooks/exhaustive-deps

  const filtered = useMemo(() => {
    const s = q.trim().toLowerCase();
    if (!s) return rows;
    return rows.filter((r) => [r.action_type, r.result, r.failure_reason, r.related_object_id, r.room, r.resident_id, r.source, r.requested_by]
      .some((v) => String(v || "").toLowerCase().includes(s)));
  }, [rows, q]);

  const openObject = (r) => {
    const t = receiptLink(r);
    if (!t) return;
    if (t.type === "route") navigate(t.value);
    else onNavigate?.(t.value);
  };

  return (
    <div data-testid="receipts-panel">
      <div className="flex flex-wrap gap-2 mb-3 items-end">
        <Input placeholder="Search action, result, id, room…" value={q} onChange={(e) => setQ(e.target.value)} className="w-64" data-testid="receipts-search" />
        <Select value={f.object_type || "__all"} onValueChange={(v) => setF({ ...f, object_type: v === "__all" ? "" : v })}>
          <SelectTrigger className="w-40" data-testid="receipts-filter-object"><SelectValue placeholder="Object type" /></SelectTrigger>
          <SelectContent>{OBJECT_TYPES.map((t) => <SelectItem key={t || "__all"} value={t || "__all"}>{t || "All objects"}</SelectItem>)}</SelectContent>
        </Select>
        <Select value={f.status || "__all"} onValueChange={(v) => setF({ ...f, status: v === "__all" ? "" : v })}>
          <SelectTrigger className="w-40" data-testid="receipts-filter-status"><SelectValue placeholder="Status" /></SelectTrigger>
          <SelectContent>{STATUSES.map((t) => <SelectItem key={t || "__all"} value={t || "__all"}>{t || "Any status"}</SelectItem>)}</SelectContent>
        </Select>
        <Input type="date" value={f.since} onChange={(e) => setF({ ...f, since: e.target.value })} data-testid="receipts-since" />
        <Input type="date" value={f.until} onChange={(e) => setF({ ...f, until: e.target.value })} data-testid="receipts-until" />
        <Button variant="ghost" onClick={load} data-testid="receipts-refresh">Refresh</Button>
        <span className="text-xs text-caos-mute ml-auto">{filtered.length} shown{rows.length >= 500 ? " (capped at 500)" : ""}</span>
      </div>

      <Card className="border-caos-line overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-caos-ambient/50 text-caos-mute text-xs uppercase tracking-wider">
              <tr>
                <th className="text-left p-2">Time</th><th className="text-left p-2">Action</th>
                <th className="text-left p-2">Object</th><th className="text-left p-2">Source</th>
                <th className="text-left p-2">Status</th><th className="text-left p-2">Where</th>
                <th className="text-left p-2">Result</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((r) => (
                <tr key={r.receipt_id} onClick={() => setSelected(r)} data-testid={`receipt-row-${r.receipt_id}`}
                    className="border-t border-caos-line hover:bg-caos-bone/60 cursor-pointer">
                  <td className="p-2 whitespace-nowrap text-caos-mute">{fmt(r.created_at)}</td>
                  <td className="p-2">{humanizeAction(r.action_type)}{r.follow_up_required && <Badge className="ml-2 bg-caos-terracotta text-white text-[9px]">follow-up</Badge>}</td>
                  <td className="p-2 text-caos-mute">{r.related_object_type || "—"}<div className="text-[10px] font-mono truncate max-w-[120px]">{r.related_object_id}</div></td>
                  <td className="p-2 text-caos-mute">{r.source}</td>
                  <td className="p-2"><Badge className={`text-[10px] uppercase ${TONE_CLASS[receiptStatusTone(r.status)]}`}>{r.status}</Badge></td>
                  <td className="p-2 text-caos-mute">{[r.room ? `Rm ${r.room}` : null, r.resident_id].filter(Boolean).join(" · ") || "—"}</td>
                  <td className="p-2 text-caos-mute truncate max-w-[220px]">{r.result || r.failure_reason || "—"}</td>
                </tr>
              ))}
              {!loading && filtered.length === 0 && (
                <tr><td colSpan={7} className="p-8 text-center text-caos-mute italic" data-testid="receipts-empty">No receipts match these filters.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </Card>

      <Dialog open={!!selected} onOpenChange={(o) => { if (!o) setSelected(null); }}>
        <DialogContent className="max-w-lg" data-testid="receipt-detail">
          <DialogHeader><DialogTitle className="font-display">{humanizeAction(selected?.action_type)}</DialogTitle></DialogHeader>
          {selected && (
            <div className="space-y-1 text-sm">
              {Object.entries(selected).filter(([, v]) => v !== null && v !== "" && v !== false).map(([k, v]) => (
                <div key={k} className="grid grid-cols-3 gap-2">
                  <span className="text-caos-mute">{k}</span>
                  <span className="col-span-2 font-mono text-xs break-all">{typeof v === "object" ? JSON.stringify(v) : String(v)}</span>
                </div>
              ))}
              {receiptLink(selected) && (
                <Button size="sm" className="bg-caos-forest mt-3" onClick={() => openObject(selected)} data-testid="receipt-open-object">
                  Open the {selected.related_object_type}
                </Button>
              )}
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
