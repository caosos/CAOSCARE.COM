import React from "react";
import { Badge } from "./ui/badge";
import { Button } from "./ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "./ui/dialog";
import { History, Pencil, X } from "lucide-react";
import { isRiderOpen, riderStatusLabel, runStatusLabel } from "../lib/transportation";

const STATUS_BADGE = {
  confirmed: "bg-caos-forest text-white",
  in_progress: "bg-caos-amber text-white",
  completed: "bg-caos-line text-caos-mute",
  cancelled: "bg-caos-line text-caos-mute line-through",
};

export default function TransportRunDetailsDialog({ run, canBook, onClose, onChange, onCancel, onHistory }) {
  if (!run) return null;
  const closeThen = (fn, rider) => {
    onClose();
    fn?.(rider);
  };

  return (
    <Dialog open={!!run} onOpenChange={(open) => { if (!open) onClose(); }}>
      <DialogContent className="max-w-xl" data-testid="transport-run-details-dialog">
        <DialogHeader>
          <DialogTitle className="font-display">Trip details</DialogTitle>
        </DialogHeader>

        <div className="flex items-center justify-between gap-3">
          <div className="font-semibold text-caos-forest">
            Pickup {run.depart_time}{run.return_time ? ` – ${run.return_time}` : ""}
          </div>
          <Badge className={STATUS_BADGE[run.status] || "bg-caos-line text-caos-mute"}>
            {runStatusLabel(run)}
          </Badge>
        </div>

        <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-2 text-sm rounded-xl border border-caos-line p-3">
          <dt className="text-caos-mute">Date</dt><dd>{run.date || run.riders?.[0]?.requested_for_date || "Not recorded"}</dd>
          <dt className="text-caos-mute">Destination</dt><dd>{run.destination || "Not recorded"}</dd>
          <dt className="text-caos-mute">Driver</dt><dd>{run.driver?.name || "Not assigned"}</dd>
          <dt className="text-caos-mute">Vehicle</dt>
          <dd>{run.vehicle?.name || "Not assigned"}{run.vehicle?.capacity != null ? ` · ${run.vehicle.capacity} seats` : ""}</dd>
        </dl>

        <div className="space-y-2">
          <div className="text-xs font-bold uppercase tracking-widest text-caos-mute">
            {run.riders.length === 1 ? "Resident" : `Residents (${run.riders.length})`}
          </div>
          {run.riders.map((rider) => (
            <div key={rider.task_id} className="rounded-xl border border-caos-line p-3" data-testid={`trip-detail-rider-${rider.task_id}`}>
              <div className="font-medium text-caos-forest">
                {rider.resident_name || rider.room || "Unknown resident"}{rider.room ? ` · Room ${rider.room}` : ""}
              </div>
              <div className="text-sm mt-1">{rider.purpose || "Purpose not recorded"}</div>
              <div className="text-xs text-caos-mute mt-1">
                {riderStatusLabel(rider)}{rider.requested_for_time_label ? ` · appointment: ${rider.requested_for_time_label}` : ""}
              </div>
              <div className="flex flex-wrap gap-2 mt-3">
                {canBook && isRiderOpen(rider) && run.status === "confirmed" && (
                  <Button size="sm" variant="outline" onClick={() => closeThen(onChange, rider)} data-testid={`trip-detail-change-${rider.task_id}`}>
                    <Pencil className="w-4 h-4 mr-1" /> Change
                  </Button>
                )}
                {canBook && isRiderOpen(rider) && (
                  <Button size="sm" variant="outline" onClick={() => closeThen(onCancel, rider)} data-testid={`trip-detail-cancel-${rider.task_id}`}>
                    <X className="w-4 h-4 mr-1" /> Cancel
                  </Button>
                )}
                <Button size="sm" variant="ghost" onClick={() => closeThen(onHistory, rider.task_id)} data-testid={`trip-detail-history-${rider.task_id}`}>
                  <History className="w-4 h-4 mr-1" /> History
                </Button>
              </div>
            </div>
          ))}
        </div>
      </DialogContent>
    </Dialog>
  );
}
