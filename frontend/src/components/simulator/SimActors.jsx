import React from "react";
import { Card } from "../ui/card";
import ActorBadge from "./ActorBadge";

// Who is in this run: the simulated cast (from the run record) and the real
// operator who started it (from the start receipt's actor fields).
export default function SimActors({ cast, startedBy, onSelect }) {
  const actors = Object.values(cast || {});
  const operator = startedBy ? {
    key: "operator", actor_id: startedBy.actor_id, name: startedBy.actor_name, role: startedBy.actor_role,
    actor_type: startedBy.actor_type, identity_basis: startedBy.identity_basis, simulated: startedBy.simulated,
  } : null;
  return (
    <Card className="border-caos-line p-4" data-testid="sim-actors">
      <h3 className="text-xs font-bold uppercase tracking-widest text-caos-mute mb-2">Actors</h3>
      {!actors.length && !operator && <div className="text-sm italic text-caos-mute">No run yet.</div>}
      <ul className="space-y-2">
        {[...actors, ...(operator ? [operator] : [])].map((a) => (
          <li key={a.key}>
            <button type="button" onClick={() => onSelect?.(a)} data-testid={`sim-actor-${a.key}`}
                    className="w-full text-left rounded border border-caos-line px-3 py-2 hover:bg-caos-bone/60">
              <div className="flex items-center gap-2">
                <ActorBadge of={a.actor_type ? a : { simulated: a.simulated }} />
                <span className="font-semibold text-caos-forest">{a.name || a.actor_id}</span>
              </div>
              <div className="text-xs text-caos-mute mt-0.5">
                {[a.key === "operator" ? "operator (started this run)" : a.role, a.department, a.room ? `Rm ${a.room}` : null,
                  a.shift ? `shift min ${a.shift.start_minute}–${a.shift.end_minute}` : null].filter(Boolean).join(" · ")}
              </div>
            </button>
          </li>
        ))}
      </ul>
    </Card>
  );
}
