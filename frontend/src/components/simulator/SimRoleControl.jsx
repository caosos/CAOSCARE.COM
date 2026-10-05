import React, { useEffect, useState } from "react";
import { api } from "../../lib/api";
import { Button } from "../ui/button";
import { toast } from "sonner";

// SIM-3: hand a staff role to a real signed-in staff member, give it back to
// its simulated actor, or leave it unassigned. The server validates the
// person (a real account that acts for the role's department) and records
// the change on the run chain; the real person then works the request in
// the normal staff UI.
export default function SimRoleControl({ roleKey, fill, onChanged }) {
  const [people, setPeople] = useState([]);
  const [pick, setPick] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api.get(`/simulator/roles/${roleKey}/candidates`)
      .then(({ data }) => setPeople(data))
      .catch(() => setPeople([]));
  }, [roleKey]);

  const assign = async (body) => {
    setBusy(true);
    try {
      await api.post(`/simulator/roles/${roleKey}`, body);
      onChanged?.();
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Could not change the role");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="mt-2 space-y-2" data-testid={`sim-role-control-${roleKey}`}>
      <div className="flex flex-wrap gap-2">
        <select value={pick} onChange={(e) => setPick(e.target.value)} disabled={busy}
                className="h-8 min-w-0 flex-1 rounded border border-caos-line bg-white px-2 text-sm"
                data-testid={`sim-role-pick-${roleKey}`}>
          <option value="">Choose a real staff member…</option>
          {people.map((p) => (
            <option key={p.user_id} value={p.user_id}>{p.name || p.user_id} ({p.role}{p.department ? ` · ${p.department}` : ""})</option>
          ))}
        </select>
        <Button size="sm" disabled={busy || !pick} className="bg-caos-forest"
                onClick={() => assign({ mode: "real", user_id: pick })} data-testid={`sim-role-real-${roleKey}`}>
          Hand to real user
        </Button>
      </div>
      <div className="flex flex-wrap gap-2">
        {fill.kind !== "simulated" && (
          <Button size="sm" variant="outline" disabled={busy} onClick={() => assign({ mode: "simulated" })}
                  data-testid={`sim-role-simulated-${roleKey}`}>
            Return to simulated
          </Button>
        )}
        {fill.kind !== "unassigned" && (
          <Button size="sm" variant="outline" disabled={busy} onClick={() => assign({ mode: "unassigned" })}
                  data-testid={`sim-role-unassigned-${roleKey}`}>
            Leave unassigned
          </Button>
        )}
      </div>
    </div>
  );
}
