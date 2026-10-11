import React, { useState } from "react";
import { api } from "../lib/api";
import { Button } from "../components/ui/button";
import { Textarea } from "../components/ui/textarea";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "../components/ui/dialog";
import { toast } from "sonner";

/**
 * Administrator review of historical open records (POST /ops/legacy/close).
 * Only items the server classified as needing review can be closed; each close
 * is receipted. A non-emergency batch takes one reason; an emergency is closed
 * one at a time and needs a written disposition (what a person confirmed).
 */
export function LegacyCloseDialog({ open, onOpenChange, kind, ids, emergency, onDone }) {
  const [reason, setReason] = useState("");
  const [disposition, setDisposition] = useState("");
  const [busy, setBusy] = useState(false);
  const submit = async () => {
    setBusy(true);
    try {
      const { data } = await api.post("/ops/legacy/close", { kind, ids, reason: reason.trim(), disposition: disposition.trim() || null });
      toast.success(`Closed ${data.closed}${data.refused.length ? ` · ${data.refused.length} refused` : ""}`);
      if (data.refused.length) toast.error(data.refused.slice(0, 3).map((r) => r.why).join("; "));
      setReason(""); setDisposition(""); onOpenChange(false); onDone?.(data);
    } catch (err) { toast.error(err?.response?.data?.detail?.[0]?.msg || err?.response?.data?.detail || "Could not close"); }
    setBusy(false);
  };
  const ready = reason.trim().length >= 3 && (!emergency || disposition.trim().length >= 3);
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md" data-testid="legacy-close-dialog">
        <DialogHeader><DialogTitle className="font-display">Close {ids.length} reviewed {kind === "alert" ? "event" : "request"}{ids.length === 1 ? "" : "s"}</DialogTitle></DialogHeader>
        <p className="text-sm text-caos-mute">They stay in history with their receipts; closing records why they are no longer open work.</p>
        <Textarea placeholder="Why these are closed (required), e.g. RF bring-up test activations, September" value={reason} onChange={(e) => setReason(e.target.value)} rows={2} data-testid="legacy-close-reason" />
        {emergency && (
          <Textarea placeholder="Emergency: what a person confirmed (required), e.g. Checked with nursing - test press, resident was fine" value={disposition} onChange={(e) => setDisposition(e.target.value)} rows={2} data-testid="legacy-close-disposition" />
        )}
        <DialogFooter><Button disabled={!ready || busy} onClick={submit} className="bg-caos-forest" data-testid="legacy-close-submit">Close as reviewed</Button></DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

/** Banner for the review view: counts, simulator state, and the batch close for non-emergencies. */
export function ReviewBanner({ currency, reviewRows, isAdmin, onClosed }) {
  const [batch, setBatch] = useState(false);
  const nonEmergency = reviewRows.filter((a) => a.severity !== "emergency").map((a) => a.alert_id);
  const sim = currency?.simulator;
  return (
    <div className="text-xs bg-[#F3F1EE] rounded-lg p-3 space-y-1" data-testid="alerts-review-banner">
      <div>Showing <strong>older items needing review</strong>: open longer than {currency?.windows?.alert_hours || 72} h, not current work. Nothing here is closed automatically.</div>
      {sim && <div data-testid="alerts-sim-state">Simulator: {sim.state === "STOPPED" ? `not running (last run ${sim.last_run_id || "none"})` : `${sim.state} run ${sim.active_run_id}`}</div>}
      {isAdmin && nonEmergency.length > 0 && (
        <Button size="sm" variant="outline" className="border-2 h-7 mt-1" onClick={() => setBatch(true)} data-testid="alerts-close-batch">
          Close the {nonEmergency.length} non-emergency items shown…
        </Button>
      )}
      <LegacyCloseDialog open={batch} onOpenChange={setBatch} kind="alert" ids={nonEmergency} emergency={false} onDone={onClosed} />
    </div>
  );
}
