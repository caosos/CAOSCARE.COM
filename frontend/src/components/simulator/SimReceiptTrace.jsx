import React, { useEffect, useState } from "react";
import { api } from "../../lib/api";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "../ui/dialog";
import { Button } from "../ui/button";
import { toast } from "sonner";
import { humanizeAction } from "../../lib/activityLog";
import { canonicalRefOf, castEntryFor, fmtTime } from "../../lib/simulator";
import ActorBadge from "./ActorBadge";

const Row = ({ k, v }) => (
  <div className="grid grid-cols-3 gap-2 text-sm">
    <span className="text-caos-mute">{k}</span>
    <span className="col-span-2 font-mono text-xs break-all">{typeof v === "object" ? JSON.stringify(v) : String(v)}</span>
  </div>
);

// Receipt -> request -> actor. Walks the chain through GET /receipts/{id}
// (parent links, and a simulator step's reference to the receipt that
// recorded the work); a task receipt opens the normal request detail.
export default function SimReceiptTrace({ receipt, cast, onClose, onOpenRequest }) {
  const [stack, setStack] = useState([]);
  useEffect(() => { setStack(receipt ? [receipt] : []); }, [receipt]);
  const r = stack[stack.length - 1];

  const follow = async (id) => {
    try {
      const { data } = await api.get(`/receipts/${id}`);
      setStack((s) => [...s, data]);
    } catch { toast.error("Could not load that receipt"); }
  };

  if (!r) return null;
  const ref = canonicalRefOf(r);
  const castEntry = castEntryFor(cast, r.actor_id);
  return (
    <Dialog open={!!receipt} onOpenChange={(o) => { if (!o) onClose(); }}>
      <DialogContent className="max-w-xl max-h-[85vh] overflow-y-auto" data-testid="sim-receipt-trace">
        <DialogHeader><DialogTitle className="font-display">{humanizeAction(r.action_type)}</DialogTitle></DialogHeader>
        <div className="text-xs text-caos-mute -mt-2 mb-2">
          {fmtTime(r.created_at)} · {r.status} · <span className="font-mono">{r.receipt_id}</span>
        </div>

        <section className="rounded border border-caos-line p-3 mb-3" data-testid="sim-trace-actor">
          <div className="flex items-center gap-2 mb-1">
            <ActorBadge of={r} />
            <span className="font-semibold text-caos-forest">{r.actor_name || r.actor_id}</span>
          </div>
          <Row k="actor id" v={r.actor_id} />
          <Row k="identity basis" v={r.identity_basis || "—"} />
          <Row k="role / department" v={[r.actor_role, r.actor_department].filter(Boolean).join(" / ") || "—"} />
          <Row k="authority" v={r.authority || "—"} />
          <Row k="channel" v={r.channel || "—"} />
          {castEntry?.shift && <Row k="shift (sim minutes)" v={`${castEntry.shift.start_minute}–${castEntry.shift.end_minute}`} />}
        </section>

        <section className="space-y-1 mb-3">
          {r.result && <Row k="result" v={r.result} />}
          {r.failure_reason && <Row k="failure" v={r.failure_reason} />}
          {r.before_state && <Row k="before" v={r.before_state} />}
          {r.after_state && <Row k="after" v={r.after_state} />}
          {r.next_state && <Row k="next state" v={r.next_state} />}
          <Row k="object" v={`${r.related_object_type || "—"} ${r.related_object_id || ""}`} />
          {r.correlation_id && <Row k="workflow (origin)" v={r.correlation_id} />}
        </section>

        <div className="flex flex-wrap gap-2">
          {stack.length > 1 && (
            <Button size="sm" variant="outline" onClick={() => setStack((s) => s.slice(0, -1))} data-testid="sim-trace-back">Back</Button>
          )}
          {r.parent_receipt_id && (
            <Button size="sm" variant="outline" onClick={() => follow(r.parent_receipt_id)} data-testid="sim-trace-parent">
              Parent receipt
            </Button>
          )}
          {ref && (
            <Button size="sm" variant="outline" onClick={() => follow(ref)} data-testid="sim-trace-canonical">
              Receipt that recorded the work
            </Button>
          )}
          {r.related_object_type === "task" && (
            <Button size="sm" className="bg-caos-forest" onClick={() => onOpenRequest(r.related_object_id)} data-testid="sim-trace-request">
              Open the request
            </Button>
          )}
          {!r.parent_receipt_id && r.correlation_id === r.receipt_id && (
            <span className="text-xs text-caos-mute self-center">This is the origin of its chain.</span>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
