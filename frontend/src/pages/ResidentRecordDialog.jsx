import React, { useEffect, useState } from "react";
import { api } from "../lib/api";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "../components/ui/dialog";
import { Badge } from "../components/ui/badge";
import { toast } from "sonner";
import ConversationSessionDetail from "./ConversationSessionDetail";

// Resident Record - Conversations (Terminal 9 "conversations must be
// first-class records"). Session-grouped view over the existing
// db.conversations turns; no copy/paste out of CAOSCARE required to
// inspect what happened in a resident's room. Profile/Family/Requests/
// Transportation sections described in the broader Resident 360 design are
// not part of this dialog yet - this ships Conversations only, the piece
// Michael asked for now.

function fmtDateTime(iso) {
  if (!iso) return "—";
  try { return new Date(iso).toLocaleString(undefined, { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" }); }
  catch { return iso; }
}

function durationLabel(startIso, endIso) {
  try {
    const ms = new Date(endIso) - new Date(startIso);
    if (ms < 1000) return "< 1 min";
    const mins = Math.round(ms / 60000);
    return mins < 1 ? "< 1 min" : `${mins} min`;
  } catch { return "—"; }
}

export default function ResidentRecordDialog({ resident, open, onOpenChange }) {
  const [sessions, setSessions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState(null);

  useEffect(() => {
    if (!resident || !open) return;
    setSelected(null);
    setLoading(true);
    api.get(`/residents/${resident.resident_id}/conversation-sessions`)
      .then(({ data }) => setSessions(data))
      .catch(() => toast.error("Could not load conversations"))
      .finally(() => setLoading(false));
  }, [resident, open]);

  if (!resident) return null;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-3xl max-h-[85vh] overflow-y-auto" data-testid="resident-record-dialog">
        <DialogHeader>
          <DialogTitle className="font-display">
            {resident.name} — Resident Record
          </DialogTitle>
        </DialogHeader>

        <h2 className="font-display text-xl font-medium text-caos-forest mb-3">Conversations</h2>

        {selected ? (
          <ConversationSessionDetail residentId={resident.resident_id} sessionId={selected} onBack={() => setSelected(null)} />
        ) : (
          <>
            {loading && <div className="text-caos-mute text-sm">Loading…</div>}
            {!loading && sessions.length === 0 && <div className="text-caos-mute text-sm">No conversations recorded yet for this resident.</div>}
            <div className="space-y-2">
              {sessions.map((s) => (
                <button
                  key={s.session_id}
                  onClick={() => setSelected(s.session_id)}
                  data-testid={`conversation-session-${s.session_id}`}
                  className="w-full text-left rounded-xl border border-caos-line p-3 hover:border-caos-forest transition-colors"
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-semibold text-caos-forest">{fmtDateTime(s.start_at)}</span>
                    <div className="flex items-center gap-2">
                      {s.is_test && <Badge variant="outline" className="text-[10px] uppercase">Test</Badge>}
                      <span className="text-xs text-caos-mute">{durationLabel(s.start_at, s.end_at)} · {s.turn_count} turns</span>
                    </div>
                  </div>
                  <div className="text-sm text-caos-ink mt-1">{s.topic || "(no topic captured)"}</div>
                  <div className="text-xs text-caos-mute mt-1">{s.room ? `Room ${s.room}` : "room unknown"} · {s.source || "unknown source"}</div>
                </button>
              ))}
            </div>
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}
