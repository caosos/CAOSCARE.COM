import React, { useCallback, useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import { api } from "../../lib/api";
import { fetchCommunityControlCapability } from "../../lib/communityControls";
import {
  resetConfirmation,
  resetErrorMessage,
  resetPayload,
} from "../../lib/communityResetControl";
import { Button } from "../ui/button";
import { Card } from "../ui/card";
import { Input } from "../ui/input";


export default function SimCommunityResetControl({ snapshot, onRuntimeRefresh }) {
  const [gate, setGate] = useState({ loadState: "loading", capability: null });
  const [confirmation, setConfirmation] = useState("");
  const [busy, setBusy] = useState(false);
  const run = snapshot?.run;
  const phrase = useMemo(() => resetConfirmation(run?.run_id || ""), [run?.run_id]);
  const loadGate = useCallback(async () => {
    setGate(await fetchCommunityControlCapability(api));
  }, []);

  useEffect(() => { loadGate(); }, [loadGate]);
  useEffect(() => { setConfirmation(""); }, [run?.run_id]);

  if (run?.state !== "STOPPED" || !run?.run_id) return null;

  const allowed = gate.capability?.mutations_allowed === true;
  const confirmed = confirmation === phrase;
  const reset = async () => {
    setBusy(true);
    try {
      await api.post(
        "/simulator/community/controls/reset",
        resetPayload(run, confirmation),
      );
      setConfirmation("");
      toast.success("Generated state removed. Historical receipts were preserved.");
    } catch (error) {
      toast.error(resetErrorMessage(error));
    } finally {
      setBusy(false);
      await Promise.all([loadGate(), onRuntimeRefresh?.()]);
    }
  };

  return (
    <Card className="border-caos-terracotta/50 p-4 sm:p-5" data-testid="community-reset-control">
      <h2 className="font-display text-xl text-caos-forest">Reset stopped simulation run</h2>
      <p className="mt-2 text-sm text-caos-mute">
        This manually removes only this run&apos;s generated community state. It never runs automatically.
        Historical receipts, real residents, and unrelated simulator runs are preserved.
      </p>
      <label className="mt-4 block text-sm font-semibold text-caos-forest" htmlFor="community-reset-confirmation">
        Type <span className="font-mono">{phrase}</span> to confirm
      </label>
      <Input
        id="community-reset-confirmation"
        className="mt-2"
        value={confirmation}
        onChange={(event) => setConfirmation(event.target.value)}
        disabled={busy}
        autoComplete="off"
        data-testid="community-reset-confirmation"
      />
      <Button
        type="button"
        variant="destructive"
        className="mt-3"
        disabled={!allowed || !confirmed || busy}
        onClick={reset}
        data-testid="community-reset-submit"
      >
        {busy ? "Resetting…" : "Reset generated state"}
      </Button>
      {!allowed && gate.loadState !== "loading" && (
        <p className="mt-2 text-xs text-caos-terracotta">
          Reset is blocked until the same transaction and index safety gate passes.
        </p>
      )}
    </Card>
  );
}
