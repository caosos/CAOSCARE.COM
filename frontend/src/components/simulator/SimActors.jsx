import React from "react";
import { Card } from "../ui/card";
import ActorBadge from "./ActorBadge";
import SimRoleControl from "./SimRoleControl";
import { roleFill } from "../../lib/simulator";

// Who is in this run: the simulated cast (from the run record), who holds
// each staff role (SIMULATED / REAL / UNASSIGNED, SIM-3), and the real
// operator who started it (from the start receipt's actor fields).
export default function SimActors({ cast, startedBy, active, onSelect, onChanged }) {
  const actors = Object.values(cast || {});
  const operator = startedBy ? {
    key: "operator", actor_id: startedBy.actor_id, name: startedBy.actor_name, role: startedBy.actor_role,
    actor_type: startedBy.actor_type, identity_basis: startedBy.identity_basis, simulated: startedBy.simulated,
  } : null;
  return (
    <Card className="border-caos-line p-4" data-testid="sim-actors">
      <h3 className="text-xs font-bold uppercase tracking-widest text-caos-mute mb-2">Actors and roles</h3>
      {!actors.length && !operator && <div className="text-sm italic text-caos-mute">No run yet.</div>}
      <ul className="space-y-2">
        {actors.map((a) => {
          const staff = a.role !== "resident";
          const fill = staff ? roleFill(a) : null;
          return (
            <li key={a.key} className="rounded border border-caos-line px-3 py-2">
              <button type="button" onClick={() => onSelect?.(a)} data-testid={`sim-actor-${a.key}`}
                      className="w-full text-left hover:opacity-80">
                <div className="flex items-center gap-2">
                  <ActorBadge kind={staff ? fill.kind : "simulated"} />
                  <span className="font-semibold text-caos-forest">{staff ? (fill.name || "No one") : a.name}</span>
                </div>
                <div className="text-xs text-caos-mute mt-0.5">
                  {[staff ? `role: ${a.role} · ${a.department}` : `resident · Rm ${a.room}`,
                    staff && fill.kind === "real" ? `normally ${a.name}` : null,
                    a.shift ? `shift min ${a.shift.start_minute}–${a.shift.end_minute}` : null].filter(Boolean).join(" · ")}
                </div>
              </button>
              {staff && active && <SimRoleControl roleKey={a.key} fill={fill} onChanged={onChanged} />}
            </li>
          );
        })}
        {operator && (
          <li className="rounded border border-caos-line px-3 py-2" data-testid="sim-actor-operator">
            <div className="flex items-center gap-2">
              <ActorBadge of={operator} />
              <span className="font-semibold text-caos-forest">{operator.name || operator.actor_id}</span>
            </div>
            <div className="text-xs text-caos-mute mt-0.5">operator (started this run)</div>
          </li>
        )}
      </ul>
    </Card>
  );
}
