import React, { useEffect, useState } from "react";
import { api } from "../lib/api";
import { useAuth } from "../lib/auth";
import { Card } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Badge } from "../components/ui/badge";
import { History, Plus, X } from "lucide-react";
import TransportAssignAction from "../components/TransportAssignAction";
import TransportRunCard from "../components/TransportRunCard";
import TransportRideForm from "../components/TransportRideForm";
import TransportCancelDialog from "../components/TransportCancelDialog";
import RequestHistoryDialog from "./RequestHistoryDialog";
import { todayLocal } from "../lib/transportation";
import { toast } from "sonner";

// Day/week transportation timeline - the same TransportRun/StaffTask data
// Aria's booking engine and the Admin daily-ops report read, shaped for a
// visual schedule. Used by Admin, Front Desk and the Transportation
// workspace (one source of truth, role-appropriate actions): front desk and
// admin book/change/cancel; they and transportation staff mark rides
// departed/completed. The backend enforces the same split.

function addDays(dateStr, n) {
  const d = new Date(`${dateStr}T00:00:00`);
  d.setDate(d.getDate() + n);
  return todayLocal(d);
}

function fmtDay(dateStr) {
  return new Date(`${dateStr}T00:00:00`).toLocaleDateString(undefined, { weekday: "short", month: "short", day: "numeric" });
}

function PendingCard({ p, canBook, onAssigned, onCancel, onHistory }) {
  return (
    <div className="rounded-xl border-2 border-caos-amber bg-caos-amber/10 p-3 mb-2" data-testid="calendar-pending-card">
      <div className="flex items-center justify-between gap-2">
        <div className="font-semibold text-caos-forest">Needs coordination</div>
        <Badge className="bg-caos-amber/20 text-caos-forest border border-caos-amber">No time yet</Badge>
      </div>
      <div className="text-sm mt-1">
        <strong>{p.resident_name || p.room || "unknown"}</strong>{p.room ? ` (${p.room})` : ""} — {p.purpose}
      </div>
      <div className="text-xs text-caos-mute">
        Resident said: {p.requested_for_time_label || "no time given"}{p.re_request_count > 0 ? ` · asked ${p.re_request_count + 1}x` : ""}
      </div>
      <div className="mt-2 flex flex-wrap gap-2">
        {canBook && <TransportAssignAction taskId={p.task_id} onAssigned={onAssigned} />}
        {canBook && (
          <Button size="sm" variant="ghost" onClick={() => onCancel(p)} data-testid={`pending-cancel-${p.task_id}`}><X className="w-4 h-4 mr-1" /> Cancel</Button>
        )}
        <Button size="sm" variant="ghost" onClick={() => onHistory(p.task_id)} data-testid={`pending-history-${p.task_id}`}><History className="w-4 h-4 mr-1" /> History</Button>
      </div>
    </div>
  );
}

// refreshKey: a parent bumps it to reload the data without remounting, so the
// day/week the staff member is looking at is not reset to today.
export default function TransportationCalendar({ refreshKey = 0 }) {
  const { user } = useAuth();
  const canBook = ["owner", "admin", "front_desk"].includes(user?.role);
  const canOperate = canBook || (user?.role === "staff" && user?.department === "transportation");
  const [date, setDate] = useState(todayLocal());
  const [view, setView] = useState("day"); // day | week
  const [data, setData] = useState(null);
  const [newRide, setNewRide] = useState(false);
  const [changeRide, setChangeRide] = useState(null);
  const [cancelRide, setCancelRide] = useState(null);
  const [historyFor, setHistoryFor] = useState(null);

  const fetchCalendar = async () => {
    try {
      const { data: d } = await api.get("/transportation/calendar", { params: { date, days: view === "week" ? 7 : 1 } });
      setData(d);
    } catch {
      toast.error("Could not load transportation calendar");
    }
  };
  useEffect(() => { fetchCalendar(); }, [date, view, refreshKey]); // eslint-disable-line react-hooks/exhaustive-deps

  const step = view === "week" ? 7 : 1;
  const withDay = (day) => (r) => ({ ...r, requested_for_date: r.requested_for_date || day.date });

  return (
    <Card className="border-caos-line p-6" data-testid="transportation-calendar-root">
      <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
        <h2 className="font-display text-xl font-medium text-caos-forest">Transportation</h2>
        <div className="flex items-center gap-2 overflow-x-auto max-w-full">
          <Button variant="outline" size="sm" className="border-2 rounded-full shrink-0" onClick={() => setDate((d) => addDays(d, -step))} data-testid="calendar-prev">←</Button>
          <Input type="date" value={date} onChange={(e) => setDate(e.target.value)} className="w-auto shrink-0" data-testid="calendar-date-picker" />
          <Button variant="outline" size="sm" className="border-2 rounded-full shrink-0" onClick={() => setDate((d) => addDays(d, step))} data-testid="calendar-next">→</Button>
          <Button variant="outline" size="sm" className={`border-2 rounded-full shrink-0 ${view === "day" ? "bg-caos-forest text-white" : ""}`} onClick={() => setView("day")} data-testid="calendar-view-day">Day</Button>
          <Button variant="outline" size="sm" className={`border-2 rounded-full shrink-0 ${view === "week" ? "bg-caos-forest text-white" : ""}`} onClick={() => setView("week")} data-testid="calendar-view-week">Week</Button>
          {canBook && (
            <Button size="sm" className="bg-caos-forest hover:bg-caos-forest-hover rounded-full shrink-0" onClick={() => setNewRide(true)} data-testid="calendar-new-ride">
              <Plus className="w-4 h-4 mr-1" /> New ride
            </Button>
          )}
        </div>
      </div>
      {!data ? (
        <div className="text-caos-mute text-sm">Loading…</div>
      ) : (
        <div className="flex gap-4 overflow-x-auto pb-2">
          {data.days.map((day) => (
            <div key={day.date} className="min-w-[260px] flex-1">
              <div className="text-xs font-bold uppercase tracking-widest text-caos-mute mb-2">{fmtDay(day.date)}</div>
              {day.runs.length === 0 && day.pending.length === 0 && <div className="text-caos-mute text-sm">Nothing scheduled.</div>}
              {day.pending.map((p) => (
                <PendingCard key={p.task_id} p={withDay(day)(p)} canBook={canBook} onAssigned={fetchCalendar}
                  onCancel={setCancelRide} onHistory={setHistoryFor} />
              ))}
              {day.runs.map((r) => (
                <TransportRunCard key={r.run_id} run={{ ...r, riders: r.riders.map(withDay(day)) }} canOperate={canOperate} canBook={canBook}
                  onChanged={fetchCalendar} onHistory={setHistoryFor} onChange={setChangeRide} onCancel={setCancelRide} />
              ))}
            </div>
          ))}
        </div>
      )}
      <TransportRideForm open={newRide} onOpenChange={setNewRide} onSaved={fetchCalendar} />
      <TransportRideForm open={!!changeRide} onOpenChange={(o) => { if (!o) setChangeRide(null); }} ride={changeRide} onSaved={fetchCalendar} />
      <TransportCancelDialog ride={cancelRide} onClose={() => setCancelRide(null)} onCancelled={fetchCalendar} />
      <RequestHistoryDialog taskId={historyFor} onClose={() => setHistoryFor(null)} />
    </Card>
  );
}
