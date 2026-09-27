import React from "react";
import StatusPill from "./StatusPill";
import { STATUS_META, STATUS_ORDER } from "../../lib/capabilities/status";

// Explains the statuses actually used on the page.
export default function StatusLegend({ items }) {
  const used = new Set(items.map((i) => i.status));
  return (
    <dl className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-sm" aria-label="What each status means">
      {STATUS_ORDER.filter((s) => used.has(s)).map((s) => (
        <div key={s} className="flex items-start gap-3">
          <dt className="shrink-0"><StatusPill status={s} /></dt>
          <dd className="text-caos-mute">{STATUS_META[s].meaning}</dd>
        </div>
      ))}
    </dl>
  );
}
