import React from "react";
import StatusPill from "./StatusPill";
import { STATUS_META, STATUS_ORDER } from "../../lib/capabilities/status";

export default function StatusLegend() {
  return (
    <dl className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-sm" aria-label="What each status means">
      {STATUS_ORDER.map((s) => (
        <div key={s} className="flex items-start gap-3">
          <dt className="shrink-0"><StatusPill status={s} /></dt>
          <dd className="text-caos-mute">{STATUS_META[s].meaning}</dd>
        </div>
      ))}
    </dl>
  );
}
