import React, { useEffect, useMemo, useState } from "react";
import { api } from "../lib/api";
import { Card } from "../components/ui/card";
import { Input } from "../components/ui/input";
import { Badge } from "../components/ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import { toast } from "sonner";
import { sourceLabel, deriveStatus, STATUS_BADGE_CLASS, fmtDateTime } from "../lib/requestDisplay";
import RequestDetailDialog from "./RequestDetailDialog";

// Communication & Requests - the operational view over resident-originated
// StaffTask records (source != "staff", i.e. not an internal daily chore).
// Same underlying collection the "Tasks" board and Resident Record read -
// no separate request store.

const STATUS_OPTIONS = ["All", "Pending", "Acknowledged", "Assigned", "Needs coordination", "Confirmed", "In progress", "Completed", "Cancelled"];
const PRIORITY_OPTIONS = ["All", "urgent", "high", "normal", "low"];

export default function RequestsBoard() {
  const [tasks, setTasks] = useState([]);
  const [selected, setSelected] = useState(null);
  const [q, setQ] = useState("");
  const [status, setStatus] = useState("All");
  const [priority, setPriority] = useState("All");
  const [department, setDepartment] = useState("All");

  const fetchAll = async () => {
    try {
      const { data } = await api.get("/tasks");
      setTasks(data.filter((t) => t.source && t.source !== "staff"));
    } catch { toast.error("Could not load requests"); }
  };
  useEffect(() => { fetchAll(); }, []);

  const departments = useMemo(() => Array.from(new Set(tasks.map((t) => t.category))).sort(), [tasks]);

  const filtered = useMemo(() => {
    return tasks
      .filter((t) => status === "All" || deriveStatus(t) === status)
      .filter((t) => priority === "All" || t.priority === priority)
      .filter((t) => department === "All" || t.category === department)
      .filter((t) => {
        if (!q.trim()) return true;
        const s = q.toLowerCase();
        return [t.resident_name, t.room, t.description, t.title].some((f) => (f || "").toLowerCase().includes(s));
      })
      .sort((a, b) => {
        // Action-needed first (not completed/cancelled), then newest first.
        const aOpen = !["Completed", "Cancelled"].includes(deriveStatus(a));
        const bOpen = !["Completed", "Cancelled"].includes(deriveStatus(b));
        if (aOpen !== bOpen) return aOpen ? -1 : 1;
        return new Date(b.created_at) - new Date(a.created_at);
      });
  }, [tasks, status, priority, department, q]);

  return (
    <Card className="border-caos-line p-6" data-testid="requests-board-root">
      <div className="mb-4">
        <h2 className="font-display text-xl font-medium text-caos-forest">Communication & requests</h2>
        <p className="text-caos-mute text-sm mt-1">Everything a resident, family member, or Front Desk has asked for — who asked, when, and where it stands.</p>
      </div>

      <div className="flex flex-wrap gap-2 mb-4">
        <Input placeholder="Search resident, room, request…" value={q} onChange={(e) => setQ(e.target.value)} className="w-64" data-testid="requests-search" />
        <Select value={status} onValueChange={setStatus}>
          <SelectTrigger className="w-44" data-testid="requests-filter-status"><SelectValue /></SelectTrigger>
          <SelectContent>{STATUS_OPTIONS.map((s) => <SelectItem key={s} value={s}>{s}</SelectItem>)}</SelectContent>
        </Select>
        <Select value={priority} onValueChange={setPriority}>
          <SelectTrigger className="w-36" data-testid="requests-filter-priority"><SelectValue /></SelectTrigger>
          <SelectContent>{PRIORITY_OPTIONS.map((p) => <SelectItem key={p} value={p}>{p === "All" ? "All priorities" : p}</SelectItem>)}</SelectContent>
        </Select>
        <Select value={department} onValueChange={setDepartment}>
          <SelectTrigger className="w-44" data-testid="requests-filter-department"><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value="All">All departments</SelectItem>
            {departments.map((d) => <SelectItem key={d} value={d}>{d}</SelectItem>)}
          </SelectContent>
        </Select>
      </div>

      <div className="space-y-2" data-testid="requests-list">
        {filtered.map((t) => {
          const ds = deriveStatus(t);
          return (
            <button
              key={t.task_id}
              onClick={() => setSelected(t.task_id)}
              data-testid={`request-row-${t.task_id}`}
              className="w-full text-left rounded-xl border border-caos-line p-3 hover:border-caos-forest transition-colors grid grid-cols-1 md:grid-cols-6 gap-2 items-center"
            >
              <div className="md:col-span-2">
                <div className="font-semibold text-caos-forest">{t.resident_name || t.room || "unknown"}{t.room && t.resident_name ? ` · Rm ${t.room}` : ""}</div>
                <div className="text-sm text-caos-ink truncate">{t.description || t.title}</div>
              </div>
              <div className="text-xs uppercase tracking-wider text-caos-mute">{t.category}</div>
              <div className="text-xs text-caos-mute">{fmtDateTime(t.created_at)}</div>
              <div className="text-xs text-caos-mute">{sourceLabel(t.source)}</div>
              <div className="flex items-center justify-between gap-2">
                <Badge className={STATUS_BADGE_CLASS[ds] || "bg-caos-mute/10 text-caos-mute"}>{ds}</Badge>
                {t.priority && t.priority !== "normal" && <Badge variant="outline" className="uppercase text-[10px]">{t.priority}</Badge>}
              </div>
            </button>
          );
        })}
        {filtered.length === 0 && <div className="text-caos-mute text-sm py-6 text-center">No requests match these filters.</div>}
      </div>

      <RequestDetailDialog taskId={selected} open={!!selected} onOpenChange={(o) => { if (!o) setSelected(null); }} onChange={fetchAll} />
    </Card>
  );
}
