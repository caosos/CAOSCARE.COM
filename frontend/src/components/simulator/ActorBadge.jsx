import React from "react";
import { ACTOR_BADGE, actorKind } from "../../lib/simulator";

// One real / simulated / system badge, from the record's own fields.
export default function ActorBadge({ of, className = "" }) {
  const b = ACTOR_BADGE[actorKind(of)];
  return (
    <span className={`inline-block rounded px-1.5 py-0.5 text-[10px] font-bold tracking-wider ${b.className} ${className}`}
          data-testid="actor-badge">
      {b.label}
    </span>
  );
}
