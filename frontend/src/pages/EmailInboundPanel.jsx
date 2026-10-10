import React, { useEffect, useRef, useState } from "react";
import { latestOnly } from "../lib/latestOnly";
import { api } from "../lib/api";
import { Card } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Badge } from "../components/ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import { Trash2, Plus } from "lucide-react";
import { toast } from "sonner";
import { inboundStatus, INBOUND_LANES } from "../lib/notificationDelivery";

// Inbound email: who may publish to the menu/activities by email (the
// allowlist, fail-closed per lane), and what happened to every email that
// arrived. Reads/writes /email/allowlist and /email/inbound/messages.
const FRESH = { state: "loading", data: [], at: null, stale: false };

// One read's truth: loading, error (never loaded), ok (loaded), or ok+stale (a later refresh failed, so the data
// shown is from the last good load, not current). An empty list is only ever asserted from a successful read.
function settle(prev, result) {
  if (result.status === "fulfilled") return { state: "ok", data: result.value.data || [], at: new Date(), stale: false };
  if (prev.at) return { ...prev, stale: true };
  return { state: "error", data: [], at: null, stale: false };
}

function ReadNotice({ what, src, onRetry }) {
  if (src.state === "loading") return <p className="text-sm text-caos-mute" data-testid={`${what}-loading`}>Loading…</p>;
  if (src.state === "error") {
    return (
      <p className="text-sm text-caos-terracotta" data-testid={`${what}-error`}>
        Could not load this. Nothing is known about it right now.{" "}
        <button type="button" className="underline font-semibold" onClick={onRetry} data-testid={`${what}-retry`}>Retry</button>
      </p>
    );
  }
  if (src.stale) {
    return (
      <p className="text-xs text-caos-terracotta mb-2" data-testid={`${what}-stale`}>
        Could not refresh. Showing the last successful load{src.at ? ` (${src.at.toLocaleTimeString()})` : ""}; it may be out of date.{" "}
        <button type="button" className="underline font-semibold" onClick={onRetry} data-testid={`${what}-retry`}>Retry</button>
      </p>
    );
  }
  return null;
}

export default function EmailInboundPanel() {
  const [allow, setAllow] = useState(FRESH);
  const [msgs, setMsgs] = useState(FRESH);
  const [form, setForm] = useState({ lane: "menu", pattern: "", label: "" });
  const guard = useRef(latestOnly());
  useEffect(() => { const g = guard.current; return () => g.invalidate(); }, []);

  const load = async () => {
    const mine = guard.current.next();   // only the newest load may update the screen; a closed panel drops late replies
    const [a, m] = await Promise.allSettled([api.get("/email/allowlist"), api.get("/email/inbound/messages?limit=50")]);
    if (!guard.current.isCurrent(mine)) return;
    setAllow((p) => settle(p, a));
    setMsgs((p) => settle(p, m));
    if (a.status === "rejected" || m.status === "rejected") toast.error("Could not load inbound email");
  };
  useEffect(() => { load(); }, []); // eslint-disable-line react-hooks/exhaustive-deps
  const entries = allow.data, messages = msgs.data;

  const add = async (e) => {
    e.preventDefault();
    try {
      await api.post("/email/allowlist", form);
      toast.success("Sender approved");
      setForm({ ...form, pattern: "", label: "" });
      load();
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Could not add sender");
    }
  };

  const remove = async (id) => {
    try {
      await api.delete(`/email/allowlist/${id}`);
      toast.success("Sender disabled");
      load();
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Could not disable sender");
    }
  };

  const active = entries.filter((e) => e.active);
  return (
    <div className="space-y-6">
      <Card className="border-caos-line p-5">
        <h3 className="font-display text-lg font-medium text-caos-forest">Approved inbound senders</h3>
        <p className="text-caos-mute text-sm mt-1 mb-4">
          Email to a department address is only used when the sender is approved for that department.
          With no approved senders, every email to it is quarantined for review.
        </p>
        <form onSubmit={add} className="flex flex-wrap gap-2 items-end mb-4" data-testid="allowlist-form">
          <Select value={form.lane} onValueChange={(v) => setForm({ ...form, lane: v })}>
            <SelectTrigger className="w-44"><SelectValue /></SelectTrigger>
            <SelectContent>
              {INBOUND_LANES.map((l) => <SelectItem key={l.value} value={l.value}>{l.label}</SelectItem>)}
            </SelectContent>
          </Select>
          <Input required className="w-64" placeholder="chef@facility.com or @facility.com"
            value={form.pattern} onChange={(e) => setForm({ ...form, pattern: e.target.value })} data-testid="allowlist-pattern" />
          <Input className="w-48" placeholder="Label (optional)"
            value={form.label} onChange={(e) => setForm({ ...form, label: e.target.value })} />
          <Button type="submit" className="bg-caos-forest rounded-full"><Plus className="w-4 h-4 mr-1" /> Approve</Button>
        </form>
        <ReadNotice what="allowlist" src={allow} onRetry={load} />
        {allow.state === "ok" && <div className="space-y-2">
          {INBOUND_LANES.map((lane) => {
            const rows = active.filter((e) => e.lane === lane.value);
            return (
              <div key={lane.value}>
                <p className="text-sm font-semibold text-caos-forest">{lane.label}</p>
                {rows.length === 0 && <p className="text-xs text-caos-terracotta" data-testid={`allowlist-empty-${lane.value}`}>No approved senders{allow.stale ? " as of the last successful load" : ""} - all email quarantined.</p>}
                {rows.map((e) => (
                  <div key={e.entry_id} className="flex items-center gap-2 text-sm py-1">
                    <span className="font-mono">{e.pattern}</span>
                    {e.label && <span className="text-caos-mute">{e.label}</span>}
                    <Button variant="ghost" size="sm" className="ml-auto" onClick={() => remove(e.entry_id)} aria-label="Disable sender">
                      <Trash2 className="w-4 h-4" />
                    </Button>
                  </div>
                ))}
              </div>
            );
          })}
        </div>}
      </Card>

      <Card className="border-caos-line p-5">
        <h3 className="font-display text-lg font-medium text-caos-forest mb-3">Inbound email received</h3>
        <ReadNotice what="inbound" src={msgs} onRetry={load} />
        {msgs.state === "ok" && <div className="space-y-2" data-testid="inbound-log">
          {messages.map((m) => {
            const s = inboundStatus(m.status);
            return (
              <div key={m.inbound_id} className="p-3 bg-caos-ambient/40 rounded-lg text-sm">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="font-mono text-xs">{m.from_address}</span>
                  <span className="text-caos-mute text-xs">to {(m.to_addresses || []).join(", ")}</span>
                  <Badge variant="outline" className={`text-xs ${s.tone}`}>{s.label}</Badge>
                  {m.routed_lane && <Badge variant="outline" className="text-xs">{m.routed_lane}</Badge>}
                  <span className="text-xs text-caos-mute ml-auto">{m.created_at ? new Date(m.created_at).toLocaleString() : ""}</span>
                </div>
                <p className="mt-1">{m.subject || "(no subject)"}</p>
                {(m.parse_notes || m.error_message) && (
                  <p className="text-xs text-caos-mute mt-1 italic">{m.error_message || m.parse_notes}</p>
                )}
              </div>
            );
          })}
          {messages.length === 0 && <p className="text-caos-mute text-sm" data-testid="inbound-empty">No inbound email has been received{msgs.stale ? " as of the last successful load" : ""}.</p>}
        </div>}
      </Card>
    </div>
  );
}
