import React, { useState } from "react";
import { api } from "../lib/api";
import { Button } from "./ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "./ui/dialog";
import { toast } from "sonner";
import TransportResourceFields, { resourcePayload } from "./TransportResourceFields";

// Shared "next action" for any transportation request still waiting for a
// time (Terminal 8 Lane C, 2026-08-23). Used by the daily-ops report
// (TransportationTab.jsx) and the calendar's pending card
// (TransportationCalendar.jsx) so the action lives in one place.
//
// Calls POST /transportation/request/{id}/assign, which uses the same
// booking engine (transportation_engine.find_or_create_run) Aria's own
// /request path uses - a staff assignment and a resident booking can never
// disagree about "booked". Never fabricates driver/vehicle capacity: if none
// is configured or free, the backend says so and this shows that reason.
//
// The resident's appointment time is shown but not copied into the pickup
// time: "a 9:30 appointment" usually means leaving earlier.
export default function TransportAssignAction({ taskId, onAssigned, size = "sm", label = "Assign" }) {
  const [open, setOpen] = useState(false);
  const [ctx, setCtx] = useState(null);
  const [form, setForm] = useState({});
  const [busy, setBusy] = useState(false);

  const openDialog = async () => {
    try {
      const { data } = await api.get(`/transportation/request/${taskId}/assign/context`);
      if (!data.resources_configured) {
        const missing = [data.drivers_configured === 0 ? "drivers" : null, data.vehicles_configured === 0 ? "vehicles" : null]
          .filter(Boolean).join(" or ");
        toast.error(`No ${missing} configured yet — add at least one under Transport resources before assigning.`);
        return;
      }
      setCtx(data);
      setForm({});
      setOpen(true);
    } catch {
      toast.error("Could not check transportation resources");
    }
  };

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    try {
      const { data } = await api.post(`/transportation/request/${taskId}/assign`, resourcePayload(form));
      if (data.booked) {
        toast.success(`Assigned — pickup ${data.run.depart_time} on ${data.run.date}${data.shared ? " (shared ride)" : ""}`);
        setOpen(false);
        onAssigned?.();
      } else {
        toast.error(data.message || "Could not assign — no matching resource");
      }
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Could not assign");
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <Button size={size} variant="outline" className="border-2 rounded-full shrink-0" onClick={openDialog} data-testid={`assign-btn-${taskId}`}>
        {label}
      </Button>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-w-lg">
          <DialogHeader><DialogTitle className="font-display">Assign a driver &amp; vehicle</DialogTitle></DialogHeader>
          {ctx && (
            <div className="rounded-xl bg-caos-bone border border-caos-line p-3 text-sm" data-testid="assign-request-summary">
              <div><strong>{ctx.purpose}</strong>{ctx.room ? ` · Room ${ctx.room}` : ""}</div>
              <div className="text-caos-mute">
                {ctx.requested_for_date} · resident said: {ctx.requested_for_time_label || "no time given"}
              </div>
            </div>
          )}
          <form onSubmit={submit} className="space-y-3">
            <TransportResourceFields value={form} onChange={setForm} requireTime />
            <DialogFooter><Button type="submit" disabled={busy} className="bg-caos-forest" data-testid="assign-confirm-btn">{busy ? "Assigning…" : "Assign"}</Button></DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </>
  );
}
