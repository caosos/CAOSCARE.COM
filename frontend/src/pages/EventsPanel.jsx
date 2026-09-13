import React, { useEffect, useMemo, useState } from "react";
import { api } from "../lib/api";
import { Card } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Badge } from "../components/ui/badge";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "../components/ui/dialog";
import { toast } from "sonner";
import { humanizeAction, eventStatusTone, fmtDuration, summarizeMetadata } from "../lib/activityLog";

const TONE_CLASS = {
  ok: "bg-caos-moss/15 text-caos-forest border border-caos-moss",
  info: "bg-caos-amber/15 text-[#8B5A20] border border-caos-amber",
  bad: "bg-caos-terracotta/15 text-caos-terracotta border border-caos-terracotta",
  muted: "bg-caos-mute/10 text-caos-mute",
};

function fmt(iso) {
  if (!iso) return "—";
  try { return new Date(iso).toLocaleString(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit", second: "2-digit" }); }
  catch { return iso; }
}

// Read-only browser over GET /events - the canonical append-only telemetry
// trace (Aria messages, tool calls, UI actions, device commands, auth).
// No new endpoint; GET /events/conversation/{id} is used to reconstruct one
// thread in order.
export default function EventsPanel() {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [f, setF] = useState({ event_type: "", room: "", resident_id: "", conversation_id: "", since: "", until: "" });
  const [q, setQ] = useState("");
  const [selected, setSelected] = useState(null);
  const [thread, setThread] = useState(null);

  const load = async () => {
    setLoading(true);
    try {
      const params = { limit: 800 };
      for (const k of ["event_type", "room", "resident_id", "conversation_id"]) if (f[k]) params[k] = f[k];
      if (f.since) params.since = `${f.since}T00:00:00+00:00`;
      if (f.until) params.until = `${f.until}T23:59:59+00:00`;
      const { data } = await api.get("/events", { params });
      setRows([...data].reverse());  // endpoint returns oldest-first; show newest-first
    } catch {
      toast.error("Could not load events");
    } finally {
      setLoading(false);
    }
  };
  useEffect(() => { load(); }, [f.event_type, f.room, f.resident_id, f.conversation_id, f.since, f.until]); // eslint-disable-line react-hooks/exhaustive-deps

  const filtered = useMemo(() => {
    const s = q.trim().toLowerCase();
    if (!s) return rows;
    return rows.filter((r) => [r.event_type, r.action, r.status, r.actor_id, r.target_id, r.target_type, r.error_message, summarizeMetadata(r.metadata)]
      .some((v) => String(v || "").toLowerCase().includes(s)));
  }, [rows, q]);

  const openThread = async (cid) => {
    try {
      const { data } = await api.get(`/events/conversation/${cid}`);
      setThread({ cid, events: data });
    } catch { toast.error("Could not load the conversation"); }
  };

  return (
    <div data-testid="events-panel">
      <div className="flex flex-wrap gap-2 mb-3 items-end">
        <Input placeholder="Search type, action, target, error…" value={q} onChange={(e) => setQ(e.target.value)} className="w-56" data-testid="events-search" />
        <Input placeholder="event_type" value={f.event_type} onChange={(e) => setF({ ...f, event_type: e.target.value })} className="w-40" data-testid="events-filter-type" />
        <Input placeholder="room" value={f.room} onChange={(e) => setF({ ...f, room: e.target.value })} className="w-24" data-testid="events-filter-room" />
        <Input placeholder="conversation_id" value={f.conversation_id} onChange={(e) => setF({ ...f, conversation_id: e.target.value })} className="w-44" data-testid="events-filter-conv" />
        <Input type="date" value={f.since} onChange={(e) => setF({ ...f, since: e.target.value })} data-testid="events-since" />
        <Input type="date" value={f.until} onChange={(e) => setF({ ...f, until: e.target.value })} data-testid="events-until" />
        <Button variant="ghost" onClick={load} data-testid="events-refresh">Refresh</Button>
        <span className="text-xs text-caos-mute ml-auto">{filtered.length} shown{rows.length >= 800 ? " (capped at 800)" : ""}</span>
      </div>

      <Card className="border-caos-line overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-caos-ambient/50 text-caos-mute text-xs uppercase tracking-wider">
              <tr>
                <th className="text-left p-2">Time</th><th className="text-left p-2">Event</th>
                <th className="text-left p-2">Source</th><th className="text-left p-2">Actor</th>
                <th className="text-left p-2">Status</th><th className="text-left p-2">Target</th>
                <th className="text-left p-2">Dur.</th><th className="text-left p-2">Detail</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((r) => (
                <tr key={r.event_id} onClick={() => setSelected(r)} data-testid={`event-row-${r.event_id}`}
                    className="border-t border-caos-line hover:bg-caos-bone/60 cursor-pointer">
                  <td className="p-2 whitespace-nowrap text-caos-mute">{fmt(r.created_at)}</td>
                  <td className="p-2">{r.event_type}{r.action && <div className="text-[10px] text-caos-mute">{r.action}</div>}</td>
                  <td className="p-2 text-caos-mute">{r.source}{r.actor_role ? ` · ${r.actor_role}` : ""}</td>
                  <td className="p-2 text-caos-mute font-mono text-[10px] truncate max-w-[100px]">{r.actor_id || "—"}</td>
                  <td className="p-2">{r.status ? <Badge className={`text-[10px] ${TONE_CLASS[eventStatusTone(r.status)]}`}>{r.status}</Badge> : "—"}</td>
                  <td className="p-2 text-caos-mute">{r.target_type || "—"}<div className="text-[10px] font-mono truncate max-w-[110px]">{r.target_id}</div></td>
                  <td className="p-2 text-caos-mute">{fmtDuration(r.duration_ms) || "—"}</td>
                  <td className="p-2 text-caos-mute truncate max-w-[220px]">{r.error_message || summarizeMetadata(r.metadata) || "—"}</td>
                </tr>
              ))}
              {!loading && filtered.length === 0 && (
                <tr><td colSpan={8} className="p-8 text-center text-caos-mute italic" data-testid="events-empty">No events match these filters.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </Card>

      <Dialog open={!!selected} onOpenChange={(o) => { if (!o) setSelected(null); }}>
        <DialogContent className="max-w-2xl max-h-[85vh] overflow-y-auto" data-testid="event-detail">
          <DialogHeader><DialogTitle className="font-display">{selected?.event_type}</DialogTitle></DialogHeader>
          {selected && (
            <div className="space-y-1 text-sm">
              {Object.entries(selected).filter(([k, v]) => k !== "metadata" && v !== null && v !== "").map(([k, v]) => (
                <div key={k} className="grid grid-cols-3 gap-2">
                  <span className="text-caos-mute">{k}</span>
                  <span className="col-span-2 font-mono text-xs break-all">{String(v)}</span>
                </div>
              ))}
              {selected.metadata && Object.keys(selected.metadata).length > 0 && (
                <div className="mt-2">
                  <div className="text-caos-mute text-xs uppercase tracking-wider mb-1">metadata</div>
                  <pre className="text-xs bg-caos-ambient/60 rounded-lg p-3 overflow-x-auto">{JSON.stringify(selected.metadata, null, 2)}</pre>
                </div>
              )}
              {selected.conversation_id && (
                <Button size="sm" variant="outline" className="border-2 mt-2" onClick={() => openThread(selected.conversation_id)} data-testid="event-open-thread">
                  View full conversation ({humanizeAction(selected.conversation_id).slice(0, 24)}…)
                </Button>
              )}
            </div>
          )}
        </DialogContent>
      </Dialog>

      <Dialog open={!!thread} onOpenChange={(o) => { if (!o) setThread(null); }}>
        <DialogContent className="max-w-2xl max-h-[85vh] overflow-y-auto" data-testid="event-thread">
          <DialogHeader><DialogTitle className="font-display">Conversation trace</DialogTitle></DialogHeader>
          <div className="space-y-2 text-sm">
            {(thread?.events || []).map((e) => (
              <div key={e.event_id} className="border-b border-caos-line pb-2">
                <div className="flex justify-between text-xs text-caos-mute">
                  <span>{fmt(e.created_at)}</span><span>{e.event_type}{e.status ? ` · ${e.status}` : ""}</span>
                </div>
                <div className="text-caos-ink/80">{e.error_message || summarizeMetadata(e.metadata) || e.action || "—"}</div>
              </div>
            ))}
            {thread && thread.events.length === 0 && <div className="text-caos-mute italic">No events in this conversation.</div>}
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
