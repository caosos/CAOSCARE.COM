import React, { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "../lib/api";
import { toast } from "sonner";
import { activeSimRequests, currentAction, failures, mergeStream, SIM_STATES } from "../lib/simulator";
import SimControls from "../components/simulator/SimControls";
import SimActors from "../components/simulator/SimActors";
import SimActivity from "../components/simulator/SimActivity";
import SimEventStream from "../components/simulator/SimEventStream";
import SimReceiptTrace from "../components/simulator/SimReceiptTrace";
import RequestDetailDialog from "./RequestDetailDialog";

// Live Operations (SIM-2): watch and control the Operations Simulator
// without a terminal. Holds no simulator state of its own - every value is
// read from the SIM-1 API (/simulator/state, /simulator/runs/{id}/history)
// and the canonical task/receipt endpoints. Polls (2s while running).
export default function LiveOperations() {
  const [state, setState] = useState(null);
  const [history, setHistory] = useState(null);
  const [tasks, setTasks] = useState([]);
  const [refused, setRefused] = useState([]);
  const [busy, setBusy] = useState(false);
  const [trace, setTrace] = useState(null);
  const [requestId, setRequestId] = useState(null);

  const load = useCallback(async () => {
    try {
      const { data: s } = await api.get("/simulator/state");
      setState(s);
      const residentId = s.cast?.resident?.actor_id;
      const [h, t, f] = await Promise.all([
        s.run_id ? api.get(`/simulator/runs/${s.run_id}/history`) : Promise.resolve({ data: null }),
        residentId ? api.get("/tasks", { params: { resident_id: residentId } }) : Promise.resolve({ data: [] }),
        api.get("/receipts", { params: { action_type: "sim_run_start_refused", limit: 5 } }),
      ]);
      setHistory(h.data);
      setTasks(t.data);
      setRefused(f.data);
    } catch {
      toast.error("Could not load the simulator state");
    }
  }, []);

  useEffect(() => {
    load();
    const t = setInterval(load, state?.state === SIM_STATES.RUNNING ? 2000 : 10000);
    return () => clearInterval(t);
  }, [load, state?.state]);

  const control = async (action) => {
    setBusy(true);
    try {
      await api.post(`/simulator/${action}`);
    } catch (err) {
      toast.error(err?.response?.data?.detail || `Could not ${action} the simulator`);
    } finally {
      setBusy(false);
      load();
    }
  };

  const runChain = history?.run_chain || [];
  const stream = useMemo(() => mergeStream(runChain, history?.request_chain), [history]); // eslint-disable-line react-hooks/exhaustive-deps
  const current = useMemo(() => currentAction(runChain), [history]); // eslint-disable-line react-hooks/exhaustive-deps
  const failed = useMemo(() => failures(runChain, refused), [history, refused]); // eslint-disable-line react-hooks/exhaustive-deps
  const requests = useMemo(() => activeSimRequests(tasks), [tasks]);
  const cast = state?.cast;

  return (
    <div className="space-y-4" data-testid="live-operations">
      <div>
        <h2 className="font-display text-2xl text-caos-forest">Live operations</h2>
        <p className="text-sm text-caos-mute">
          The Operations Simulator, demo room only. Simulated actors act through the same request and task
          services as real staff; every action has a receipt you can trace back to where it started.
        </p>
      </div>
      <SimControls state={state} busy={busy} onControl={control} />
      <div className="grid gap-4 lg:grid-cols-3">
        <div className="space-y-4 min-w-0">
          <SimActors cast={cast} startedBy={state?.started_by}
                     onSelect={(a) => { const r = stream.find((x) => x.actor_id === a.actor_id); if (r) setTrace(r); }} />
          <SimActivity current={current} requests={requests} failed={failed}
                       onOpenReceipt={setTrace} onOpenRequest={setRequestId} />
        </div>
        <div className="lg:col-span-2 min-w-0">
          <SimEventStream rows={stream} currentId={current?.receipt_id} onSelect={setTrace} />
        </div>
      </div>
      <SimReceiptTrace receipt={trace} cast={cast} onClose={() => setTrace(null)}
                       onOpenRequest={(id) => { setTrace(null); setRequestId(id); }} />
      <RequestDetailDialog taskId={requestId} open={!!requestId}
                           onOpenChange={(o) => { if (!o) setRequestId(null); }} onChange={load} />
    </div>
  );
}
