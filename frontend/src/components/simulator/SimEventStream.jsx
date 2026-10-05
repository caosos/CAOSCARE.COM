import React from "react";
import { Card } from "../ui/card";
import { humanizeAction } from "../../lib/activityLog";
import { fmtTime } from "../../lib/simulator";
import ActorBadge from "./ActorBadge";

// The run chain and the request chain merged, newest first. Each row is a
// canonical receipt; clicking opens the trace.
export default function SimEventStream({ rows, currentId, onSelect }) {
  return (
    <Card className="border-caos-line p-4" data-testid="sim-event-stream">
      <h3 className="text-xs font-bold uppercase tracking-widest text-caos-mute mb-2">Receipt / event stream</h3>
      {!rows.length && <div className="text-sm italic text-caos-mute">No receipts yet.</div>}
      <ul className="divide-y divide-caos-line">
        {rows.map((r) => (
          <li key={r.receipt_id}>
            <button type="button" onClick={() => onSelect(r)} data-testid={`sim-event-${r.receipt_id}`}
                    className={`w-full text-left py-2 px-1 hover:bg-caos-bone/60 ${r.receipt_id === currentId ? "bg-caos-amber/10" : ""}`}>
              <div className="flex flex-wrap items-center gap-2 text-sm">
                <span className="text-xs text-caos-mute w-20 shrink-0">{fmtTime(r.created_at)}</span>
                <span className={`text-[10px] uppercase tracking-wider ${r.chain === "run" ? "text-caos-mute" : "text-caos-forest font-bold"}`}>
                  {r.chain === "run" ? "simulator" : "request"}
                </span>
                <span className="font-medium">{humanizeAction(r.action_type)}</span>
                {r.status === "failed" && <span className="text-[10px] font-bold text-caos-terracotta">FAILED</span>}
                <ActorBadge of={r} className="ml-auto" />
              </div>
              <div className="text-xs text-caos-mute ml-[5.5rem] truncate">
                {r.actor_name || r.actor_id}{r.authority ? ` · ${r.authority}` : ""}{r.result || r.failure_reason ? ` · ${r.result || r.failure_reason}` : ""}
              </div>
            </button>
          </li>
        ))}
      </ul>
    </Card>
  );
}
