import React, { useEffect, useState } from "react";
import { api } from "../lib/api";
import { Card } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Badge } from "../components/ui/badge";
import TransportAssignAction from "../components/TransportAssignAction";
import { toast } from "sonner";

// Day/week transportation timeline - the same TransportRun/StaffTask data
// Aria's booking engine and the Admin daily-ops report read, just shaped
// for a visual schedule. Used by both Admin and Front Desk (Section 9: one
// source of truth, role-appropriate views) - never fetch or compute this
// independently elsewhere.

function todayLocal() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

function addDays(dateStr, n) {
  const d = new Date(`${dateStr}T00:00:00`);
  d.setDate(d.getDate() + n);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

function fmtDay(dateStr) {
  return new Date(`${dateStr}T00:00:00`).toLocaleDateString(undefined, { weekday: "short", month: "short", day: "numeric" });
}

const STATUS_BADGE = {
  confirmed: "bg-caos-forest text-white",
  in_progress: "bg-caos-forest text-white",
  completed: "bg-caos-line text-caos-mute",
  cancelled: "bg-caos-line text-caos-mute line-through",
};

function RunCard({ run }) {
  return (
    <div className="rounded-xl border border-caos-line p-3 mb-2">
      <div className="flex items-center justify-between gap-2">
        <div className="font-semibold text-caos-forest">{run.depart_time}{run.return_time ? ` – ${run.return_time}` : ""}</div>
        <Badge className={STATUS_BADGE[run.status] || "bg-caos-line text-caos-mute"}>{run.status.replace("_", " ")}</Badge>
      </div>
      <div className="text-xs text-caos-mute mt-1">
        {run.destination || "destination not given"} · {run.driver?.name || "no driver assigned"} · {run.vehicle?.name || "no vehicle assigned"}
        {run.vehicle?.capacity != null && ` (cap ${run.vehicle.capacity})`}
      </div>
      <div className="text-sm mt-2 space-y-0.5">
        {run.riders.map((r) => (
          <div key={r.task_id}>
            <strong>{r.resident_name || r.room || "unknown"}</strong>{r.room ? ` (${r.room})` : ""} — {r.purpose}
          </div>
        ))}
        {run.riders.length > 1 && <div className="text-xs text-caos-forest">Shared run — {run.riders.length} residents</div>}
      </div>
    </div>
  );
}

function PendingCard({ p, onAssigned }) {
  return (
    <div className="rounded-xl border-2 border-caos-amber bg-caos-amber/10 p-3 mb-2" data-testid="calendar-pending-card">
      <div className="flex items-center justify-between gap-2">
        <div className="font-semibold text-caos-forest">Needs coordination</div>
        <Badge className="bg-caos-amber/20 text-caos-forest border border-caos-amber">Pending</Badge>
      </div>
      <div className="text-sm mt-1">
        <strong>{p.resident_name || p.room || "unknown"}</strong>{p.room ? ` (${p.room})` : ""} — {p.purpose}
      </div>
      <div className="mt-2">
        <TransportAssignAction taskId={p.task_id} onAssigned={onAssigned} />
      </div>
    </div>
  );
}

function DayColumn({ day, onAssigned }) {
  const hasAny = day.runs.length > 0 || day.pending.length > 0;
  return (
    <div className="min-w-[260px] flex-1">
      <div className="text-xs font-bold uppercase tracking-widest text-caos-mute mb-2">{fmtDay(day.date)}</div>
      {!hasAny && <div className="text-caos-mute text-sm">Nothing scheduled.</div>}
      {day.runs.map((r) => <RunCard key={r.run_id} run={r} />)}
      {day.pending.map((p) => <PendingCard key={p.task_id} p={p} onAssigned={onAssigned} />)}
    </div>
  );
}

export default function TransportationCalendar() {
  const [date, setDate] = useState(todayLocal());
  const [view, setView] = useState("day"); // day | week
  const [data, setData] = useState(null);

  const fetchCalendar = async () => {
    try {
      const { data: d } = await api.get("/transportation/calendar", { params: { date, days: view === "week" ? 7 : 1 } });
      setData(d);
    } catch {
      toast.error("Could not load transportation calendar");
    }
  };
  useEffect(() => { fetchCalendar(); }, [date, view]); // eslint-disable-line react-hooks/exhaustive-deps

  const step = view === "week" ? 7 : 1;

  return (
    <Card className="border-caos-line p-6" data-testid="transportation-calendar-root">
      <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
        <h2 className="font-display text-xl font-medium text-caos-forest">Transportation calendar</h2>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" className="border-2 rounded-full" onClick={() => setDate((d) => addDays(d, -step))} data-testid="calendar-prev">←</Button>
          <Input type="date" value={date} onChange={(e) => setDate(e.target.value)} className="w-auto" data-testid="calendar-date-picker" />
          <Button variant="outline" size="sm" className="border-2 rounded-full" onClick={() => setDate((d) => addDays(d, step))} data-testid="calendar-next">→</Button>
          <Button variant="outline" size="sm" className={`border-2 rounded-full ${view === "day" ? "bg-caos-forest text-white" : ""}`} onClick={() => setView("day")} data-testid="calendar-view-day">Day</Button>
          <Button variant="outline" size="sm" className={`border-2 rounded-full ${view === "week" ? "bg-caos-forest text-white" : ""}`} onClick={() => setView("week")} data-testid="calendar-view-week">Week</Button>
        </div>
      </div>
      {!data ? (
        <div className="text-caos-mute text-sm">Loading…</div>
      ) : (
        <div className="flex gap-4 overflow-x-auto pb-2">
          {data.days.map((day) => <DayColumn key={day.date} day={day} onAssigned={fetchCalendar} />)}
        </div>
      )}
    </Card>
  );
}
