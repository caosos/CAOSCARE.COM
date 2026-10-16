import { useCallback, useEffect, useState } from "react";
import { api } from "../../lib/api";
import { fetchCommunityRuntimeSnapshot } from "../../lib/communityRuntimeLoad";
import SimCommunityControls from "../simulator/SimCommunityControls";

// The simulation run's clock and the existing guarded run controls
// (start/pause/resume/stop/step) — the same component Live Operations uses;
// the controls stay disabled unless the server's safety gate allows them.
export default function SimulationBox() {
  const [snap, setSnap] = useState(null);
  const [failed, setFailed] = useState(false);
  const load = useCallback(async () => {
    const r = await fetchCommunityRuntimeSnapshot(api);
    if (r.loadState === "ready") { setSnap(r.snapshot); setFailed(false); } else { setFailed(true); }
  }, []);
  useEffect(() => {
    load();
    const t = setInterval(load, snap?.run?.state === "RUNNING" ? 3000 : 10000);
    return () => clearInterval(t);
  }, [load, snap?.run?.state]);

  const run = snap?.run;
  const clock = snap?.clock || run?.clock;
  return (
    <div className="mt-2 space-y-3 text-[14px] text-[#374151]" data-testid="ws-simulation">
      {failed && !snap && <p className="text-[#B42318]">Simulation status could not be read.</p>}
      {snap && !run && <p>No simulation run exists yet.</p>}
      {run && (
        <p>
          <span className="font-semibold text-[#111827]">{run.state}</span>
          {clock?.day != null ? ` · Simulated day ${clock.day}${clock.hh_mm ? `, ${clock.hh_mm}` : ""}` : ""}
        </p>
      )}
      {snap && <SimCommunityControls snapshot={snap} onRuntimeRefresh={load} />}
    </div>
  );
}
