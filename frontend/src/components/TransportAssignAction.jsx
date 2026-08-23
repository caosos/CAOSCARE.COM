import React, { useState } from "react";
import { api } from "../lib/api";
import { Button } from "./ui/button";
import { Input } from "./ui/input";
import { Label } from "./ui/label";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "./ui/dialog";
import { toast } from "sonner";

// Shared "next action" for any transportation request stuck at
// "Pending — no slot yet" (Terminal 8 Lane C fix, 2026-08-23). Used by both
// the daily-ops report (TransportationTab.jsx) and the calendar's pending
// card (TransportationCalendar.jsx) so there is exactly one place this
// action is implemented, per the project's one-source-of-truth rule.
//
// Calls the same POST /transportation/request/{id}/assign endpoint, which
// itself reuses the identical booking engine call
// (transportation_engine.find_or_create_run) Aria's own /request path
// uses — a staff assignment and a resident-requested booking can never
// disagree about what counts as "booked". Never fabricates driver/vehicle
// capacity: if none is configured, the backend says so and this shows that
// reason verbatim instead of a generic failure.
export default function TransportAssignAction({ taskId, onAssigned, size = "sm", label = "Assign" }) {
  const [open, setOpen] = useState(false);
  const [startTime, setStartTime] = useState("10:00");
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
      setOpen(true);
    } catch {
      toast.error("Could not check transportation resources");
    }
  };

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    try {
      const { data } = await api.post(`/transportation/request/${taskId}/assign`, { start_time: startTime });
      if (data.booked) {
        toast.success(`Assigned — ${data.run.depart_time} on ${data.run.date}${data.shared ? " (shared run)" : ""}`);
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
        <DialogContent className="max-w-sm">
          <DialogHeader><DialogTitle className="font-display">Assign a driver &amp; vehicle</DialogTitle></DialogHeader>
          <form onSubmit={submit} className="space-y-3">
            <div>
              <Label>Pickup time</Label>
              <Input type="time" required value={startTime} onChange={(e) => setStartTime(e.target.value)} data-testid="assign-time-input" />
            </div>
            <p className="text-caos-mute text-xs">
              Checks the same driver/vehicle availability the booking engine uses — this will only confirm if a free pair actually exists for this time.
            </p>
            <DialogFooter><Button type="submit" disabled={busy} className="bg-caos-forest" data-testid="assign-confirm-btn">{busy ? "Assigning…" : "Assign"}</Button></DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </>
  );
}
