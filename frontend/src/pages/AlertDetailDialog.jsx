import React, { useEffect, useState } from "react";
import { api } from "../lib/api";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "../components/ui/dialog";
import { Button } from "../components/ui/button";
import { Textarea } from "../components/ui/textarea";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Badge } from "../components/ui/badge";
import { Clock, CheckCircle2, AlertCircle, MessageSquare } from "lucide-react";
import { toast } from "sonner";

export default function AlertDetailDialog({ alertId, open, onOpenChange, onChanged }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [outcome, setOutcome] = useState("");
  const [notes, setNotes] = useState("");

  useEffect(() => {
    if (!open || !alertId) return;
    (async () => {
      setLoading(true);
      try {
        const { data: d } = await api.get(`/alerts/${alertId}`);
        setData(d);
        setOutcome(d.alert.outcome || "");
        setNotes(d.alert.close_notes || "");
      } catch {
        toast.error("Failed to load");
      } finally { setLoading(false); }
    })();
  }, [open, alertId]);

  const close = async () => {
    if (!outcome.trim()) {
      toast.error("Outcome required");
      return;
    }
    try {
      await api.post(`/alerts/${alertId}/close`, { outcome, close_notes: notes });
      toast.success("Event closed");
      onOpenChange(false);
      onChanged?.();
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Failed");
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto" data-testid="alert-detail-dialog">
        <DialogHeader>
          <DialogTitle className="font-display">Event timeline</DialogTitle>
        </DialogHeader>

        {loading && <div className="py-8 text-center text-caos-mute">Loading…</div>}

        {data && (
          <div className="space-y-6">
            {/* Summary */}
            <div className="bg-caos-ambient rounded-xl p-4">
              <div className="flex items-center gap-2 flex-wrap">
                <Badge className="uppercase tracking-wider font-bold bg-caos-terracotta text-white">
                  {data.alert.severity}
                </Badge>
                <Badge variant="outline" className="uppercase tracking-wider text-xs">{data.alert.status}</Badge>
                {data.alert.escalation_level > 0 && (
                  <Badge className="bg-caos-amber text-white">
                    Escalation Lv {data.alert.escalation_level}
                  </Badge>
                )}
              </div>
              <h3 className="font-display text-2xl mt-3 text-caos-forest">
                {data.alert.resident_name || "Unknown resident"}
              </h3>
              <p className="text-caos-mute text-sm mt-1">
                Room {data.alert.room || "—"} · {data.alert.zone || "Location unknown"} · via {data.alert.triggered_by.replace("_", " ")}
              </p>
              {data.alert.message && (
                <p className="mt-2 italic text-caos-ink/70">"{data.alert.message}"</p>
              )}
            </div>

            {/* Timeline */}
            <section>
              <h4 className="font-display font-medium text-caos-forest mb-3 flex items-center gap-2">
                <Clock className="w-4 h-4" /> Timeline
              </h4>
              <div className="relative border-l-2 border-caos-line ml-2 pl-5 space-y-4">
                {data.timeline.map((t, i) => (
                  <div key={i} className="relative">
                    <div className="absolute -left-[1.65rem] top-1 w-4 h-4 rounded-full bg-caos-forest border-4 border-caos-bone" />
                    <p className="font-semibold text-caos-forest">{t.label}</p>
                    <p className="text-caos-mute text-sm">{new Date(t.at).toLocaleString()}</p>
                    <p className="text-caos-ink/70 text-sm">{t.detail}</p>
                  </div>
                ))}
              </div>
            </section>

            {/* Chat */}
            {data.chat && data.chat.length > 0 && (
              <section>
                <h4 className="font-display font-medium text-caos-forest mb-3 flex items-center gap-2">
                  <MessageSquare className="w-4 h-4" /> Recent companion chat
                </h4>
                <div className="bg-white border border-caos-line rounded-xl p-3 max-h-48 overflow-y-auto text-sm space-y-2">
                  {data.chat.slice(-10).map((m, i) => (
                    <div key={i} className={m.role === "assistant" ? "text-caos-forest" : "text-caos-ink/60"}>
                      <span className="text-xs font-bold uppercase tracking-wider">{m.role === "assistant" ? "CAOS" : "Resident"}: </span>
                      {m.content}
                    </div>
                  ))}
                </div>
              </section>
            )}

            {/* Close-out */}
            {data.alert.status !== "resolved" && (
              <section className="bg-caos-ambient rounded-xl p-4 space-y-3">
                <h4 className="font-display font-medium text-caos-forest flex items-center gap-2">
                  <CheckCircle2 className="w-4 h-4" /> Close out with outcome
                </h4>
                <div>
                  <Label>Outcome (required)</Label>
                  <Input
                    data-testid="close-outcome"
                    value={outcome}
                    onChange={(e) => setOutcome(e.target.value)}
                    placeholder="Assisted to bathroom / Brought water / False alarm / Transferred to ER"
                  />
                </div>
                <div>
                  <Label>Notes</Label>
                  <Textarea
                    data-testid="close-notes"
                    value={notes}
                    onChange={(e) => setNotes(e.target.value)}
                    placeholder="Any additional context, follow-up needed, handoff info…"
                  />
                </div>
              </section>
            )}

            {data.alert.status === "resolved" && data.alert.outcome && (
              <section className="bg-caos-ambient rounded-xl p-4">
                <p className="text-xs font-bold uppercase tracking-widest text-caos-mute">Outcome recorded</p>
                <p className="font-display text-lg text-caos-forest mt-1">{data.alert.outcome}</p>
                {data.alert.close_notes && (
                  <p className="text-caos-ink/70 mt-2">{data.alert.close_notes}</p>
                )}
              </section>
            )}
          </div>
        )}

        <DialogFooter>
          {data?.alert?.status !== "resolved" && (
            <Button onClick={close} className="bg-caos-moss hover:bg-caos-moss/90 text-white" data-testid="close-event-btn">
              Close event
            </Button>
          )}
          <Button variant="outline" onClick={() => onOpenChange(false)}>Done</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
