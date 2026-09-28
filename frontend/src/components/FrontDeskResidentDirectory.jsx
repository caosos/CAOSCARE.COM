import React, { useEffect, useMemo, useState } from "react";
import { api } from "../lib/api";
import { Card } from "./ui/card";
import { Input } from "./ui/input";
import { Button } from "./ui/button";
import { Badge } from "./ui/badge";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "./ui/dialog";
import { Plus, Bus, History } from "lucide-react";
import { toast } from "sonner";
import { deriveStatus, STATUS_BADGE_CLASS, fmtDateTime } from "../lib/requestDisplay";
import RequestHistoryDialog from "../pages/RequestHistoryDialog";

const OPEN = ["pending", "in_progress"];

// Front desk's resident directory: find a resident fast, see what they have
// open right now, start a request or a ride for them, and read their request
// history. Reads the same /residents and /tasks records every other screen
// uses.
export default function FrontDeskResidentDirectory({ reloadKey, onNewRequest, onNewRide }) {
  const [residents, setResidents] = useState([]);
  const [tasks, setTasks] = useState([]);
  const [q, setQ] = useState("");
  const [historyOf, setHistoryOf] = useState(null);
  const [historyTask, setHistoryTask] = useState(null);

  useEffect(() => {
    api.get("/residents").then(({ data }) => setResidents(data)).catch(() => toast.error("Could not load residents"));
    api.get("/tasks").then(({ data }) => setTasks(data.filter((t) => t.resident_id))).catch(() => setTasks([]));
  }, [reloadKey]);

  const byResident = useMemo(() => {
    const m = {};
    tasks.forEach((t) => { (m[t.resident_id] = m[t.resident_id] || []).push(t); });
    return m;
  }, [tasks]);

  const shown = useMemo(() => {
    const s = q.trim().toLowerCase();
    return residents
      .filter((r) => !s || [r.name, r.preferred_name, r.room].some((f) => (f || "").toLowerCase().includes(s)))
      .sort((a, b) => String(a.room).localeCompare(String(b.room), undefined, { numeric: true }));
  }, [residents, q]);

  const history = historyOf ? (byResident[historyOf.resident_id] || []) : [];

  return (
    <Card className="border-caos-line p-6" data-testid="front-desk-residents">
      <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
        <h2 className="font-display text-xl font-medium text-caos-forest">Residents ({residents.length})</h2>
        <Input placeholder="Search name or room…" value={q} onChange={(e) => setQ(e.target.value)} className="w-64 max-w-full" data-testid="fd-resident-search" />
      </div>
      <div className="divide-y divide-caos-line">
        {shown.map((r) => {
          const open = (byResident[r.resident_id] || []).filter((t) => OPEN.includes(t.status));
          const rides = open.filter((t) => t.category === "transportation").length;
          return (
            <div key={r.resident_id} className="py-3 flex flex-wrap items-center justify-between gap-3" data-testid={`fd-resident-${r.resident_id}`}>
              <div className="min-w-0">
                <div className="font-semibold text-caos-forest">
                  {r.name}{r.preferred_name && <span className="text-caos-mute text-xs font-normal"> "{r.preferred_name}"</span>}
                </div>
                <div className="text-xs text-caos-mute">
                  Room {r.room || "—"} · {open.length - rides} open request{open.length - rides === 1 ? "" : "s"} · {rides} open ride{rides === 1 ? "" : "s"}
                </div>
              </div>
              <div className="flex gap-1.5 shrink-0">
                <Button size="sm" variant="outline" className="border-2" onClick={() => onNewRequest(r.resident_id)} data-testid={`fd-new-request-${r.resident_id}`}><Plus className="w-4 h-4 mr-1" /> Request</Button>
                <Button size="sm" variant="outline" className="border-2" onClick={() => onNewRide(r.resident_id)} data-testid={`fd-new-ride-${r.resident_id}`}><Bus className="w-4 h-4 mr-1" /> Ride</Button>
                <Button size="sm" variant="ghost" onClick={() => setHistoryOf(r)} data-testid={`fd-history-${r.resident_id}`}><History className="w-4 h-4 mr-1" /> History</Button>
              </div>
            </div>
          );
        })}
        {shown.length === 0 && <div className="text-caos-mute text-sm py-6 text-center">No residents match.</div>}
      </div>

      <Dialog open={!!historyOf} onOpenChange={(o) => { if (!o) setHistoryOf(null); }}>
        <DialogContent className="max-w-lg max-h-[85vh] overflow-y-auto">
          <DialogHeader><DialogTitle className="font-display">{historyOf?.name} — requests</DialogTitle></DialogHeader>
          {history.length === 0 && <div className="text-caos-mute text-sm">No requests on record.</div>}
          <div className="space-y-2">
            {history.map((t) => (
              <button key={t.task_id} onClick={() => setHistoryTask(t.task_id)} data-testid={`fd-history-row-${t.task_id}`}
                className="w-full text-left rounded-xl border border-caos-line p-2.5 hover:border-caos-forest transition-colors">
                <div className="flex items-center justify-between gap-2">
                  <span className="font-medium text-caos-forest truncate">{t.title}</span>
                  <Badge className={STATUS_BADGE_CLASS[deriveStatus(t)] || ""}>{deriveStatus(t)}</Badge>
                </div>
                <div className="text-xs text-caos-mute">{t.category} · {fmtDateTime(t.created_at)}{t.requested_for_date ? ` · for ${t.requested_for_date}` : ""}</div>
              </button>
            ))}
          </div>
        </DialogContent>
      </Dialog>
      <RequestHistoryDialog taskId={historyTask} onClose={() => setHistoryTask(null)} />
    </Card>
  );
}
