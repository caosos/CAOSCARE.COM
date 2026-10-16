import { useEffect, useState } from "react";
import { api } from "../lib/api";

// CO-008: the simulator's Transportation work is "Scheduled simulated transport
// coordination" tickets — coordination routines, not ride requests (no date,
// slot, run, driver or vehicle). Counted here separately from ride bookings,
// with the same query as the workspace metrics (GET /ops/metrics/records).
export default function TransportCoordinationNote() {
  const [counts, setCounts] = useState(null);
  useEffect(() => {
    const total = (metric) => api.get("/ops/metrics/records", { params: { world: "simulated", metric,
      department: "transportation", origin: "scheduled_routine", page_size: 1 } }).then(({ data }) => data.total);
    Promise.all([total("open"), total("done")])
      .then(([open, done]) => setCounts({ open, done }))
      .catch(() => setCounts(null));   // no simulation run (or not allowed): say nothing
  }, []);
  if (!counts) return null;
  return (
    <div className="rounded-xl border border-caos-line bg-white px-4 py-3 text-[14px]" data-testid="transport-coordination-note">
      <b>Simulator coordination tasks:</b> {counts.done} completed on the current simulated day, {counts.open} open now.
      <span className="text-caos-mute"> These are coordination routines handled by SIM drivers — not ride requests and not bookings.
      The simulator does not book rides (the booking path is not simulation-isolated yet), so ride bookings below come only
      from real requests.</span>
    </div>
  );
}
