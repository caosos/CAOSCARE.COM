import React, { useCallback, useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import { api } from "../../lib/api";
import {
  controlErrorMessage,
  fetchCommunityControlCapability,
  sendCommunityControl,
} from "../../lib/communityControls";
import { Badge } from "../ui/badge";
import { Button } from "../ui/button";
import { Card } from "../ui/card";


const STATE_CLASS = {
  RUNNING: "border-caos-moss bg-caos-moss/20 text-caos-forest",
  PAUSED: "border-caos-amber bg-caos-amber/20 text-[#8B5A20]",
  STOPPED: "border-caos-line bg-caos-mute/10 text-caos-mute",
};

const ACTIONS = {
  RUNNING: ["pause", "stop"],
  // A stopped run keeps its history; a new run can be created beside it.
  STOPPED: ["create_paused"],
};

const LABELS = {
  create_paused: "Create paused run",
  provision_residents: "Set up residents",
  resume: "Resume community",
  pause: "Pause community",
  stop: "Stop community",
  step: "Step one event",
};

export default function SimCommunityControls({ snapshot, onRuntimeRefresh }) {
  const [gate, setGate] = useState({ loadState: "loading", capability: null });
  const [busy, setBusy] = useState(null);

  const loadGate = useCallback(async () => {
    setGate(await fetchCommunityControlCapability(api));
  }, []);

  useEffect(() => { loadGate(); }, [loadGate]);

  const run = snapshot?.run;
  const state = run?.state;
  const notStarted = run?.status === "not_started";
  const readiness = run?.resident_readiness;
  const residentsReady = readiness?.status === "ready"
    && readiness?.residents_provisioned === true;
  const needsResidents = readiness?.status === "not_provisioned"
    && readiness?.residents_provisioned === false;
  const actions = useMemo(
    () => {
      if (notStarted) return ["create_paused"];
      if (state === "PAUSED") {
        return [
          ...(needsResidents ? ["provision_residents"] : []),
          "resume", "step", "stop",
        ];
      }
      return ACTIONS[state] || [];
    },
    [needsResidents, notStarted, state],
  );
  const capability = gate.capability;
  const allowed = capability?.mutations_allowed === true;
  const advertised = capability?.available_actions || [];
  const disabledReasons = capability?.blockers?.map((item) => item.message) || [];
  if (gate.loadState === "error") {
    disabledReasons.push("Control capability could not be verified. No mutation is allowed.");
  }
  if (!notStarted && !["RUNNING", "PAUSED", "STOPPED"].includes(state)) {
    disabledReasons.push("Exact Living Community run state is unavailable.");
  }

  const act = async (action) => {
    setBusy(action);
    try {
      await sendCommunityControl(api, action, run);
      toast.success(`${LABELS[action]} accepted with receipt-backed state.`);
    } catch (error) {
      toast.error(controlErrorMessage(error, `${LABELS[action]} was refused`));
    } finally {
      setBusy(null);
      await Promise.all([loadGate(), onRuntimeRefresh?.()]);
    }
  };

  return (
    <Card className="border-caos-line p-4 sm:p-5" data-testid="community-controls">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="font-display text-2xl text-caos-forest">Living Community controls</h2>
          <p className="mt-1 text-sm text-caos-mute">
            These controls operate the receipt-backed 90-day community. They are separate from the legacy demo simulator below.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Badge variant="outline">NOT LEGACY DEMO</Badge>
          <Badge
            variant="outline"
            className={state ? STATE_CLASS[state] : "border-caos-line text-caos-mute"}
            data-testid="community-control-state"
          >
            {state || (notStarted ? "NOT STARTED" : "UNKNOWN")}
          </Badge>
        </div>
      </header>

      <div className="mt-4 rounded-lg border border-caos-line bg-white p-3 text-sm">
        <p className="font-semibold text-caos-forest">Safety gate</p>
        {gate.loadState === "loading" ? (
          <p className="text-caos-mute">Checking explicit enablement and a real read-only MongoDB transaction…</p>
        ) : allowed ? (
          <p className="text-caos-forest" data-testid="community-controls-enabled">
            Enabled: explicit flag, transactional read, and required named indexes are verified.
          </p>
        ) : (
          <ul className="mt-1 list-disc pl-5 text-caos-terracotta" data-testid="community-controls-blockers">
            {disabledReasons.map((reason) => <li key={reason}>{reason}</li>)}
          </ul>
        )}
      </div>

      <div className="mt-4 flex flex-wrap gap-2">
        {actions.map((action) => (
          <Button
            key={action}
            type="button"
            variant={action === "stop" ? "outline" : "default"}
            disabled={!allowed || !advertised.includes(action) || busy !== null
              || (["resume", "step"].includes(action) && !residentsReady)}
            onClick={() => act(action)}
            data-testid={`community-control-${action}`}
          >
            {busy === action ? "Working…" : LABELS[action]}
          </Button>
        ))}
        <Button type="button" variant="ghost" onClick={loadGate} disabled={busy !== null}>
          Recheck safety gate
        </Button>
      </div>
      {state === "PAUSED" && (
        <p className="mt-2 text-sm text-caos-mute" data-testid="community-resident-readiness">
          {residentsReady
            ? "Resident gate ready: ten canonical burn-in residents have exact run-bound receipts."
            : needsResidents
              ? "Next: provision the ten simulated burn-in residents. Resume stays disabled until that receipt-backed step succeeds."
              : "Resident readiness is unknown or invalid. Refresh runtime truth before provisioning, resuming, or stepping."}
        </p>
      )}
      {capability?.step?.enabled !== true && (
        <p className="mt-2 text-xs text-caos-mute" data-testid="community-step-reason">
          Step is disabled: {capability?.step?.reason || "the safety gate has not been verified."}
        </p>
      )}
      {state === "STOPPED" && (
        <p className="mt-2 text-sm text-caos-mute">This run is stopped. Its history and receipts remain available. Create a new run to start again.</p>
      )}
    </Card>
  );
}
