import React, { useState } from "react";
import { toast } from "sonner";
import { api } from "../../lib/api";
import { titleCase } from "../../lib/dashboardFormat";
import { Button } from "../ui/button";

// Cover / hand back one simulated worker's shift (SIM-006). The server
// receipts both with the signed-in person as the actor.
export default function CoverShiftButton({ runId, worker, covered, onChanged, size = "sm" }) {
  const [saving, setSaving] = useState(false);
  if (!runId || !worker?.actor_id) return null;
  const toggle = async () => {
    setSaving(true);
    try {
      await api.post(`/simulator/community/shift-cover${covered ? "/end" : ""}`,
                     { run_id: runId, worker_actor_id: worker.actor_id });
      toast.success(covered
        ? `${worker.name}'s shift handed back`
        : `You are covering ${worker.name}'s shift. Use Work as ${titleCase(worker.department)} to work their tickets.`);
      onChanged?.();
    } catch (err) {
      toast.error(err?.response?.data?.detail?.message || "Could not change the shift cover");
    } finally {
      setSaving(false);
    }
  };
  return (
    <Button type="button" size={size} variant="outline" disabled={saving} onClick={toggle}
            data-testid={`cover-${worker.actor_id}`}>
      {covered ? "End cover" : "Cover shift"}
    </Button>
  );
}
