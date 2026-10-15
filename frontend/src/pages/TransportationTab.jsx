import React, { useEffect, useState } from "react";
import { api } from "../lib/api";
import { Card } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Badge } from "../components/ui/badge";
import TransportAssignAction from "../components/TransportAssignAction";
import TransportUnresolvedList from "../components/TransportUnresolvedList";
import RequestDetailDialog from "./RequestDetailDialog";
import TransportRideForm from "../components/TransportRideForm";
import DepartmentRoster from "../components/DepartmentRoster";
import TransportCoordinationNote from "../components/TransportCoordinationNote";
import { Plus } from "lucide-react";
import { toast } from "sonner";

function fmtDateTime(iso) {
  if (!iso) return "unknown";
  try {
    return new Date(iso).toLocaleString(undefined, { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" });
  } catch {
    return iso;
  }
}

function todayLocal() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

function Section({ title, children }) {
  return (
    <div className="mb-6">
      <h3 className="font-display text-sm font-bold uppercase tracking-widest text-caos-mute mb-2">{title}</h3>
      {children}
    </div>
  );
}

export default function TransportationTab() {
  const [date, setDate] = useState(todayLocal());
  const [report, setReport] = useState(null);
  const [error, setError] = useState(null);
  const [showUnresolved, setShowUnresolved] = useState(false);
  const [openId, setOpenId] = useState(null);
  const [newRide, setNewRide] = useState(false);

  const fetchReport = async () => {
    try {
      const { data } = await api.get("/transportation/report", { params: { date } });
      setReport(data); setError(null);
    } catch (err) {
      setError(err?.response?.status === 403 ? "Transportation is open to administrators, the front desk and transportation staff." : "Could not load the transportation report.");
    }
  };
  useEffect(() => { fetchReport(); }, [date]); // eslint-disable-line react-hooks/exhaustive-deps

  const seedSlots = async () => {
    try {
      const { data } = await api.post("/transportation/slots/seed-two-weeks");
      toast.success(`Created ${data.created} slots`);
      fetchReport();
    } catch { toast.error("Could not seed slots"); }
  };

  if (error && !report) return (
    <Card className="border-caos-line p-6 text-sm" data-testid="transport-report-error">{error} <Button size="sm" variant="outline" className="ml-2" onClick={fetchReport}>Try again</Button></Card>
  );
  if (!report) return <Card className="border-caos-line p-6">Loading…</Card>;
  const s = report.summary;

  return (
    <div className="space-y-4">
    <DepartmentRoster department="transportation" label="Transportation" />
    <TransportCoordinationNote />
    <Card className="border-caos-line p-6" data-testid="transportation-tab-root">
      <div className="flex flex-wrap justify-between items-start gap-y-3 mb-4">
        <div>
          <h2 className="font-display text-xl font-medium text-caos-forest">Transportation — daily operations</h2>
          <p className="text-caos-mute text-sm mt-1">What came in, what went out, what's still open — one day at a time. Start a ride with New ride,
            book a pickup with Book on any waiting ride, and open Unresolved to see every ride still waiting, on any date.</p>
        </div>
        <div className="flex items-center gap-3 overflow-x-auto max-w-full">
          <Input type="date" value={date} onChange={(e) => setDate(e.target.value)} className="w-auto shrink-0" data-testid="transport-date-picker" />
          <Button className="bg-caos-forest hover:bg-caos-forest-hover rounded-full shrink-0" onClick={() => setNewRide(true)} data-testid="transport-new-ride">
            <Plus className="w-4 h-4 mr-1" /> New ride
          </Button>
          <Button variant="outline" className="border-2 rounded-full shrink-0" onClick={seedSlots} data-testid="seed-slots-btn">Seed 2-week schedule</Button>
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mb-6">
        {[
          ["Requests", s.total_requests_received], ["Booked", s.total_booked], ["Completed", s.total_completed],
          ["Cancelled", s.total_cancelled], ["Unresolved", s.total_unresolved],
        ].map(([label, val]) => label === "Unresolved" ? (
          <button key={label} type="button" onClick={() => setShowUnresolved((v) => !v)} title={s.unresolved_scope || ""}
            className={`rounded-xl border-2 p-3 text-center hover:shadow-sm ${showUnresolved ? "border-caos-forest" : "border-caos-amber/60"}`} data-testid="transport-unresolved-tile">
            <div className="text-2xl font-display text-caos-forest">{val}</div>
            <div className="text-xs uppercase tracking-wider text-caos-mute">{label} · any date</div>
          </button>
        ) : (
          <div key={label} className="rounded-xl border border-caos-line p-3 text-center">
            <div className="text-2xl font-display text-caos-forest">{val}</div>
            <div className="text-xs uppercase tracking-wider text-caos-mute">{label}</div>
          </div>
        ))}
      </div>
      {error && <div className="text-xs text-red-700 mb-3" data-testid="transport-report-stale">{error} Showing the last loaded report.</div>}
      {showUnresolved && (
        <TransportUnresolvedList rows={report.current_state.waiting_unbooked} scope={s.unresolved_scope}
          onOpen={setOpenId} onAssigned={fetchReport} onClose={() => setShowUnresolved(false)} />
      )}
      {s.utilization != null && (
        <div className="text-sm text-caos-mute mb-6">Slot utilization: {s.slot_booked}/{s.slot_capacity} ({Math.round(s.utilization * 100)}%)</div>
      )}

      <Section title={`Inbound (${report.inbound.length})`}>
        {report.inbound.length === 0 && <div className="text-caos-mute text-sm">No requests received.</div>}
        {report.inbound.map((i) => (
          <div key={i.task_id} className="text-sm py-2 border-b border-caos-line last:border-0 flex items-start justify-between gap-3">
            <div>
              <strong>{i.room || i.resident_id || "unknown"}</strong> — {i.purpose}
              <div className="text-caos-mute text-xs mt-0.5">
                Requested at {fmtDateTime(i.received_at)} · Appointment {i.requested_for_date} ({i.requested_for_time_label || "no time given"}) · via {i.source}
              </div>
            </div>
            <div className="flex items-center gap-2 shrink-0">
              <Badge className={i.booked ? "bg-caos-forest text-white shrink-0" : "bg-caos-amber/20 text-caos-forest border border-caos-amber shrink-0"}>
                {i.booked ? "Booked" : "Pending — no slot yet"}
              </Badge>
              {!i.booked && <TransportAssignAction taskId={i.task_id} onAssigned={fetchReport} />}
            </div>
          </div>
        ))}
      </Section>

      <Section title={`Outbound / actions (${report.outbound.length})`}>
        {report.outbound.length === 0 && <div className="text-caos-mute text-sm">No actions recorded.</div>}
        {report.outbound.map((o, idx) => (
          <div key={idx} className="text-sm py-1 border-b border-caos-line last:border-0 flex gap-2 items-center">
            <Badge variant="outline">{o.action}</Badge> <span>{o.room || o.resident_id || "unknown"}</span>
          </div>
        ))}
      </Section>

      <Section title="Current state">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-sm">
          <div>
            <div className="font-semibold mb-1">Upcoming rides ({report.current_state.upcoming_rides.length})</div>
            {report.current_state.upcoming_rides.map((r) => <button type="button" key={r.task_id} className="block text-left text-caos-mute hover:underline" onClick={() => setOpenId(r.task_id)}>{r.resident_name || r.room} — {r.requested_for_date}</button>)}
          </div>
          <div>
            <button type="button" className="font-semibold mb-1 underline" onClick={() => setShowUnresolved(true)} data-testid="transport-waiting-open">Waiting / unbooked ({report.current_state.waiting_unbooked.length})</button>
            {report.current_state.waiting_unbooked.map((r) => <button type="button" key={r.task_id} className="block text-left text-caos-mute hover:underline" onClick={() => setOpenId(r.task_id)}>{r.resident_name || r.room} — {r.requested_for_date || "no date"}</button>)}
          </div>
          <div>
            <div className="font-semibold mb-1">Follow-ups required ({report.current_state.follow_ups_required.length})</div>
            {report.current_state.follow_ups_required.map((r) => <button type="button" key={r.task_id} className="block text-left text-caos-mute hover:underline" onClick={() => setOpenId(r.task_id)}>{r.resident_name || r.room} — asked {r.times_asked}x</button>)}
          </div>
        </div>
            </Section>
      <TransportRideForm open={newRide} onOpenChange={setNewRide} onSaved={fetchReport} />
      <RequestDetailDialog taskId={openId} open={!!openId} onOpenChange={(o) => { if (!o) setOpenId(null); }} onChange={fetchReport} />
    </Card>
    </div>
  );
}
