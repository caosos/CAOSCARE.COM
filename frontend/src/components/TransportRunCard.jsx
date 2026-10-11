import React from "react";
import { api } from "../lib/api";
import { Badge } from "./ui/badge";
import { Button } from "./ui/button";
import { Eye, History, Pencil, Play, Check, X } from "lucide-react";
import { toast } from "sonner";
import { runActions, runStatusLabel, riderStatusLabel, isRiderOpen } from "../lib/transportation";

const STATUS_BADGE = {
  confirmed: "bg-caos-forest text-white",
  in_progress: "bg-caos-amber text-white",
  completed: "bg-caos-line text-caos-mute",
  cancelled: "bg-caos-line text-caos-mute line-through",
};

// One confirmed ride on the calendar: time, driver, vehicle, riders, and the
// real lifecycle actions. Depart/Complete post to /transportation/runs/*,
// which update every rider's request and write a receipt for each.
export default function TransportRunCard({ run, canOperate, canBook, onOpen, onChanged, onHistory, onChange, onCancel }) {
  const actions = runActions(run, { canOperate });
  const act = async (path, body) => {
    try {
      await api.post(`/transportation/runs/${run.run_id}/${path}`, body);
      toast.success(path === "depart" ? "Marked departed" : "Ride completed");
      onChanged?.();
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Action failed");
    }
  };

  return (
    <div className="rounded-xl border border-caos-line p-3 mb-2" data-testid={`run-${run.run_id}`}>
      <button type="button" className="block w-full text-left rounded-lg focus:outline-none focus:ring-2 focus:ring-caos-forest/40"
        onClick={() => onOpen?.(run)} data-testid={`run-open-${run.run_id}`} aria-label={`Open trip details for ${run.depart_time}`}>
        <div className="flex items-center justify-between gap-2">
          <div className="font-semibold text-caos-forest">Pickup {run.depart_time}{run.return_time ? ` – ${run.return_time}` : ""}</div>
          <Badge className={STATUS_BADGE[run.status] || "bg-caos-line text-caos-mute"}>{runStatusLabel(run)}</Badge>
        </div>
        <div className="text-xs text-caos-mute mt-1">
          {run.destination || "destination not given"} · {run.driver?.name || "no driver"} · {run.vehicle?.name || "no vehicle"}
          {run.vehicle?.capacity != null && ` (seats ${run.vehicle.capacity})`}
        </div>
        <div className="text-sm mt-2 space-y-1.5">
          {run.riders.map((r) => (
            <div key={r.task_id} className="min-w-0" data-testid={`rider-${r.task_id}`}>
              <strong>{r.resident_name || r.room || "unknown"}</strong>{r.room ? ` (${r.room})` : ""} — {r.purpose}
              <div className="text-xs text-caos-mute">
                {riderStatusLabel(r)}{r.requested_for_time_label ? ` · said: ${r.requested_for_time_label}` : ""}
              </div>
            </div>
          ))}
          {run.riders.length > 1 && <div className="text-xs text-caos-forest">Shared ride — {run.riders.length} residents</div>}
        </div>
        <div className="text-xs font-medium text-caos-forest mt-2 flex items-center gap-1">
          <Eye className="w-3.5 h-3.5" /> Open trip details
        </div>
      </button>
      <div className="text-sm mt-2 space-y-1.5">
        {run.riders.map((r) => (
          <div key={r.task_id} className="flex justify-end gap-1" data-testid={`rider-actions-${r.task_id}`}>
              {canBook && isRiderOpen(r) && run.status === "confirmed" && (
                <Button size="sm" variant="ghost" className="h-7 px-2" onClick={() => onChange(r)} data-testid={`rider-change-${r.task_id}`} title="Change">
                  <Pencil className="w-3.5 h-3.5" />
                </Button>
              )}
              {canBook && isRiderOpen(r) && (
                <Button size="sm" variant="ghost" className="h-7 px-2" onClick={() => onCancel(r)} data-testid={`rider-cancel-${r.task_id}`} title="Cancel">
                  <X className="w-3.5 h-3.5" />
                </Button>
              )}
              <Button size="sm" variant="ghost" className="h-7 px-2" onClick={() => onHistory(r.task_id)} data-testid={`rider-history-${r.task_id}`} title="History">
                <History className="w-3.5 h-3.5" />
              </Button>
          </div>
        ))}
      </div>
      {(actions.depart || actions.complete) && (
        <div className="flex gap-2 mt-3">
          {actions.depart && (
            <Button size="sm" className="bg-caos-forest hover:bg-caos-forest-hover" onClick={() => act("depart")} data-testid={`run-depart-${run.run_id}`}>
              <Play className="w-4 h-4 mr-1" /> Departed
            </Button>
          )}
          {actions.complete && (
            <Button size="sm" variant="outline" className="border-2" onClick={() => act("complete", {})} data-testid={`run-complete-${run.run_id}`}>
              <Check className="w-4 h-4 mr-1" /> Ride completed
            </Button>
          )}
        </div>
      )}
    </div>
  );
}
