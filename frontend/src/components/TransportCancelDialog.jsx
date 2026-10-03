import React, { useState } from "react";
import { api } from "../lib/api";
import { Button } from "./ui/button";
import { Textarea } from "./ui/textarea";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "./ui/dialog";
import { toast } from "sonner";

// Staff cancels one resident's ride with a reason. The reason is kept on the
// request and its receipt, and is what Aria reads back if the resident asks.
export default function TransportCancelDialog({ ride, onClose, onCancelled }) {
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  if (!ride) return null;

  const submit = async () => {
    setBusy(true);
    try {
      await api.post(`/transportation/staff/request/${ride.task_id}/cancel`, { reason: reason.trim() || null });
      toast.success("Ride cancelled");
      setReason("");
      onClose();
      onCancelled?.();
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Could not cancel the ride");
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog open={!!ride} onOpenChange={(o) => { if (!o) onClose(); }}>
      <DialogContent className="max-w-md">
        <DialogHeader><DialogTitle className="font-display">Cancel ride — {ride.resident_name || ride.room || ride.purpose}</DialogTitle></DialogHeader>
        <p className="text-sm text-caos-mute">{ride.purpose}{ride.requested_for_date ? ` · ${ride.requested_for_date}` : ""}</p>
        <Textarea placeholder="Reason (the resident can hear this if they ask)" value={reason}
          onChange={(e) => setReason(e.target.value)} rows={3} data-testid="ride-cancel-reason" />
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>Keep ride</Button>
          <Button onClick={submit} disabled={busy} className="bg-caos-terracotta hover:bg-caos-terracotta/90 text-white" data-testid="ride-cancel-confirm">
            {busy ? "Cancelling…" : "Cancel ride"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
