import React from "react";
import { Card } from "../ui/card";
import { Badge } from "../ui/badge";
import { deriveStatus, STATUS_BADGE_CLASS } from "../../lib/requestDisplay";
import { humanizeAction } from "../../lib/activityLog";
import { fmtTime } from "../../lib/simulator";

// Current action, active simulated requests (the canonical task records,
// shown with the same status model as the staff boards) and failures.
export default function SimActivity({ current, requests, failed, onOpenReceipt, onOpenRequest }) {
  return (
    <Card className="border-caos-line p-4 space-y-4" data-testid="sim-activity">
      <section>
        <h3 className="text-xs font-bold uppercase tracking-widest text-caos-mute mb-1">Current action</h3>
        {current ? (
          <button type="button" onClick={() => onOpenReceipt(current)} data-testid="sim-current-action"
                  className="text-left text-sm hover:underline">
            {fmtTime(current.created_at)} · {current.result || current.failure_reason || humanizeAction(current.action_type)}
          </button>
        ) : <div className="text-sm italic text-caos-mute">No step executed yet.</div>}
      </section>
      <section>
        <h3 className="text-xs font-bold uppercase tracking-widest text-caos-mute mb-1">Active simulated requests</h3>
        {!requests.length && <div className="text-sm italic text-caos-mute">None open.</div>}
        <ul className="space-y-1">
          {requests.map((t) => {
            const ds = deriveStatus(t);
            return (
              <li key={t.task_id}>
                <button type="button" onClick={() => onOpenRequest(t.task_id)} data-testid={`sim-request-${t.task_id}`}
                        className="w-full text-left rounded border border-caos-line px-3 py-2 hover:bg-caos-bone/60">
                  <div className="flex items-center gap-2 text-sm">
                    <Badge className={STATUS_BADGE_CLASS[ds]}>{ds}</Badge>
                    <span className="font-medium truncate">{t.title}</span>
                  </div>
                  <div className="text-xs text-caos-mute">
                    {t.category} · Rm {t.room}{t.assigned_name ? ` · ${t.assigned_name}` : " · unassigned"}
                  </div>
                </button>
              </li>
            );
          })}
        </ul>
      </section>
      <section>
        <h3 className="text-xs font-bold uppercase tracking-widest text-caos-mute mb-1">Failures / blocked</h3>
        {!failed.length && <div className="text-sm italic text-caos-mute">None.</div>}
        <ul className="space-y-1">
          {failed.map((r) => (
            <li key={r.receipt_id}>
              <button type="button" onClick={() => onOpenReceipt(r)} data-testid={`sim-failure-${r.receipt_id}`}
                      className="w-full text-left text-sm text-caos-terracotta hover:underline">
                {fmtTime(r.created_at)} · {humanizeAction(r.action_type)} — {r.failure_reason || r.result}
              </button>
            </li>
          ))}
        </ul>
      </section>
    </Card>
  );
}
