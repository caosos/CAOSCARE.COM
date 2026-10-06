import React, { useEffect, useState } from "react";
import { toast } from "sonner";
import { api } from "../../lib/api";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "../ui/dialog";
import { humanizeAction } from "../../lib/activityLog";
import { orderChain, receiptTrust } from "../../lib/agentOps";
import { fmtTime } from "../../lib/simulator";
import ActorBadge from "../simulator/ActorBadge";
import StatusBadge from "./StatusBadge";

const TRUST_TONE = { verified: "ok", simulated: "sim", unverified: "warn", failed: "bad" };
const Row = ({ k, v }) => (
  <div className="grid grid-cols-3 gap-2 text-xs">
    <span className="text-caos-mute">{k}</span>
    <span className="col-span-2 font-mono break-all">{typeof v === "object" ? JSON.stringify(v) : String(v ?? "—")}</span>
  </div>
);

// The command's receipts in chain order (origin first), each with who acted,
// on what authority, what changed, and how much it proves.
export default function ReceiptChainDialog({ commandId, onClose }) {
  const [data, setData] = useState(null);
  useEffect(() => {
    if (!commandId) { setData(null); return; }
    api.get(`/agent-control/commands/${commandId}`)
      .then(({ data: d }) => setData(d))
      .catch(() => { toast.error("Could not load the receipt chain"); onClose(); });
  }, [commandId]); // eslint-disable-line react-hooks/exhaustive-deps

  const chain = orderChain(data?.receipts || []);
  return (
    <Dialog open={!!commandId} onOpenChange={(o) => { if (!o) onClose(); }}>
      <DialogContent className="max-w-2xl max-h-[85vh] overflow-y-auto" data-testid="receipt-chain">
        <DialogHeader>
          <DialogTitle className="font-display">Receipt chain</DialogTitle>
          <DialogDescription className="sr-only">Every receipt for this command, origin first.</DialogDescription>
        </DialogHeader>
        {data && (
          <p className="text-xs text-caos-mute -mt-2 mb-2 break-words">
            <span className="font-mono">{data.command.command_id}</span> → {data.command.target_agent_id}:
            “{data.command.instruction}”
          </p>
        )}
        <ol className="space-y-3">
          {chain.map((r, i) => {
            const trust = receiptTrust(r);
            return (
              <li key={r.receipt_id} className="rounded border border-caos-line p-3" data-testid={`chain-${i}`}>
                <div className="mb-1 flex flex-wrap items-center gap-2">
                  <span className="text-xs text-caos-mute">{i + 1}.</span>
                  <span className="font-semibold text-caos-forest">{humanizeAction(r.action_type)}</span>
                  <ActorBadge of={r} />
                  <StatusBadge label={trust.toUpperCase()} tone={TRUST_TONE[trust]} testId={`chain-trust-${i}`} />
                  <span className="text-xs text-caos-mute">{fmtTime(r.created_at)}</span>
                </div>
                <Row k="receipt" v={r.receipt_id} />
                <Row k="actor" v={`${r.actor_name || r.actor_id} (${r.identity_basis || "—"})`} />
                <Row k="authority" v={r.authority} />
                <Row k="parent" v={r.parent_receipt_id} />
                {r.before_state && <Row k="before" v={r.before_state} />}
                {r.after_state && <Row k="after" v={r.after_state} />}
                {r.result && <Row k="result" v={r.result} />}
                {r.failure_reason && <Row k="failure" v={r.failure_reason} />}
              </li>
            );
          })}
        </ol>
      </DialogContent>
    </Dialog>
  );
}
