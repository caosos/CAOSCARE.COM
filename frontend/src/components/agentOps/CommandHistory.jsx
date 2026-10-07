import React from "react";
import { Button } from "../ui/button";
import { commandSummary } from "../../lib/agentOps";
import { fmtTime } from "../../lib/simulator";
import StatusBadge from "./StatusBadge";

const TONE = { acknowledged: "ok", completed: "ok", delivered: "warn", queued: "mute", failed: "bad", cancelled: "mute" };

// Recent commands for the selected agent: what was asked and what came back.
export default function CommandHistory({ commands, onInspect }) {
  if (!commands.length) {
    return <p className="text-sm text-caos-mute" data-testid="command-history-empty">No commands yet.</p>;
  }
  return (
    <ul className="space-y-2" data-testid="command-history">
      {commands.map((c) => {
        const s = commandSummary(c);
        return (
          <li key={c.command_id} className="rounded border border-caos-line p-3 text-sm" data-testid={`command-${c.command_id}`}>
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="flex items-center gap-2">
                <StatusBadge label={s.status.toUpperCase()} tone={TONE[s.status]} />
                <span className="text-xs text-caos-mute">
                  {fmtTime(c.created_at)} · by {c.issued_by?.name || c.issued_by?.user_id}
                </span>
              </div>
              <Button size="sm" variant="outline" onClick={() => onInspect(c.command_id)}
                      data-testid={`inspect-${c.command_id}`}>
                Receipts ({s.steps})
              </Button>
            </div>
            <p className="mt-2 whitespace-pre-wrap break-words">{s.asked}</p>
            {s.reply && <p className="mt-1 text-caos-mute break-words">↳ {s.reply}</p>}
          </li>
        );
      })}
    </ul>
  );
}
