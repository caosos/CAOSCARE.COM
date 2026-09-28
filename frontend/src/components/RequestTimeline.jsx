import React from "react";
import { buildRequestTimeline } from "../lib/requestHistory";

const when = (at) => (at ? new Date(at).toLocaleString() : "—");

// Shared request history: each step and note from the task's event_log
// (see lib/requestHistory.js), then the receipts filed against it.
// Used by the department queue's History dialog and the admin request detail.
export default function RequestTimeline({ task, receipts = [] }) {
  const events = buildRequestTimeline(task);
  return (
    <>
      <div className="space-y-1.5 text-sm" data-testid="request-history-timeline">
        {events.map((e, i) => (
          <div key={i} className="flex gap-3">
            <span className="text-xs text-caos-mute w-40 shrink-0">{when(e.at)}</span>
            <div className="min-w-0">
              <div>{e.label}</div>
              {e.text && (
                <div className={`text-caos-ink/80 whitespace-pre-wrap ${e.kind === "note" ? "" : "italic"}`}>
                  {e.kind === "note" ? e.text : `"${e.text}"`}
                </div>
              )}
            </div>
          </div>
        ))}
      </div>
      {receipts.length > 0 && (
        <details className="mt-3" data-testid="request-history-receipts">
          <summary className="text-xs font-bold uppercase tracking-widest text-caos-mute cursor-pointer">
            Receipts ({receipts.length})
          </summary>
          <div className="mt-1 space-y-0.5 text-xs text-caos-mute">
            {receipts.map((r) => (
              <div key={r.receipt_id} className="flex gap-3">
                <span className="w-40 shrink-0">{when(r.created_at)}</span>
                <span>{r.action_type.replace(/_/g, " ")} · {r.status}</span>
              </div>
            ))}
          </div>
        </details>
      )}
    </>
  );
}
