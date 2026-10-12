import React from "react";
import { Badge } from "./ui/badge";
import { Button } from "./ui/button";
import TransportAssignAction from "./TransportAssignAction";

/**
 * The open ride requests behind the "Unresolved" count (GET /transportation/report → current_state.waiting_unbooked).
 * Same records the count is computed from; every row opens the real request (owner, status, receipt trail) and keeps
 * the existing Book action. Nothing is copied or stored here.
 */
export default function TransportUnresolvedList({ rows, scope, onOpen, onAssigned, onClose }) {
  return (
    <div className="mb-6 rounded-xl border-2 border-caos-amber/60 p-4" data-testid="transport-unresolved-list">
      <div className="flex items-start justify-between gap-3 mb-2">
        <div>
          <h3 className="font-display text-lg text-caos-forest">Unresolved rides ({rows.length})</h3>
          {scope && <p className="text-xs text-caos-mute">{scope}</p>}
        </div>
        <Button size="sm" variant="ghost" onClick={onClose} data-testid="transport-unresolved-close">Close</Button>
      </div>
      {rows.length === 0 && <div className="text-sm text-caos-mute italic" data-testid="transport-unresolved-empty">No open ride request is waiting for a booking.</div>}
      <div className="space-y-2">
        {rows.map((r) => (
          <div key={r.task_id} className="rounded-lg border border-caos-line p-3 text-sm" data-testid={`transport-unresolved-${r.task_id}`}>
            <div className="flex flex-wrap items-start justify-between gap-2">
              <div className="min-w-0">
                <div className="font-semibold text-caos-forest break-words">{r.resident_name || r.room || "Unknown resident"}{r.room && r.resident_name ? ` · Room ${r.room}` : ""} — {r.purpose}</div>
                <div className="text-xs text-caos-mute mt-0.5">
                  {[r.requested_for_date ? `for ${r.requested_for_date}${r.requested_for_time_label ? ` (${r.requested_for_time_label})` : ""}` : "no date",
                    r.owner ? `owner ${r.owner}` : "no owner", r.status, r.times_asked > 1 ? `asked ${r.times_asked}x` : null,
                    r.age_hours != null ? `open ${r.age_hours < 48 ? `${r.age_hours}h` : `${Math.floor(r.age_hours / 24)}d`}` : null].filter(Boolean).join(" · ")}
                </div>
                <div className="text-xs mt-1" data-testid={`transport-unresolved-next-${r.task_id}`}>Next: {r.next_action}</div>
              </div>
              <div className="flex items-center gap-2 shrink-0">
                {r.currency?.bucket === "review" && <Badge variant="outline" className="text-[10px]" title={r.currency.reason}>older</Badge>}
                <TransportAssignAction taskId={r.task_id} onAssigned={onAssigned} />
                <Button size="sm" className="bg-caos-forest" onClick={() => onOpen(r.task_id)} data-testid={`transport-unresolved-open-${r.task_id}`}>Open</Button>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
