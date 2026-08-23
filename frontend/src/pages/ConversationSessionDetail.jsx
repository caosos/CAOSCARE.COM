import React, { useEffect, useState } from "react";
import { api } from "../lib/api";
import { Button } from "../components/ui/button";
import { Badge } from "../components/ui/badge";
import { toast } from "sonner";
import RequestDetailDialog from "./RequestDetailDialog";

// The "complete chronological exchange" view for one conversation session -
// turns, requests/receipts created, device actions (best-effort, room+time
// matched), and the voice-diagnostic metadata that lets a suspect/echo turn
// be investigated without opening browser dev tools. Reuses the existing
// conversations/receipts/tasks/realtime_diagnostics records; nothing new is
// stored here.

function fmtTime(iso) {
  if (!iso) return "—";
  try { return new Date(iso).toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit", second: "2-digit" }); }
  catch { return iso; }
}

export default function ConversationSessionDetail({ residentId, sessionId, onBack }) {
  const [data, setData] = useState(null);
  const [openTaskId, setOpenTaskId] = useState(null);

  useEffect(() => {
    api.get(`/residents/${residentId}/conversation-sessions/${sessionId}`)
      .then(({ data: d }) => setData(d))
      .catch(() => toast.error("Could not load conversation"));
  }, [residentId, sessionId]);

  if (!data) return <div className="text-caos-mute text-sm py-6">Loading…</div>;

  return (
    <div data-testid="conversation-detail-root">
      <Button variant="ghost" size="sm" onClick={onBack} className="mb-3" data-testid="conversation-back-btn">← Back to conversations</Button>

      <div className="mb-4">
        <h3 className="font-display text-lg font-medium text-caos-forest mb-2">Transcript</h3>
        <div className="space-y-2 max-h-80 overflow-y-auto border border-caos-line rounded-xl p-3">
          {data.turns.map((t, i) => (
            <div key={i} className={`text-sm ${t.role === "assistant" ? "text-caos-forest" : "text-caos-ink"}`}>
              <span className="text-xs text-caos-mute mr-2">{fmtTime(t.created_at)}</span>
              <strong>{t.role === "assistant" ? "Aria" : "Resident"}:</strong> {t.content}
              {t.trusted === false && <Badge className="ml-2 bg-caos-amber/20 text-caos-forest border border-caos-amber text-[10px]">unconfirmed audio</Badge>}
            </div>
          ))}
          {data.turns.length === 0 && <div className="text-caos-mute text-sm">No turns recorded.</div>}
        </div>
      </div>

      <div className="mb-4">
        <h3 className="font-display text-lg font-medium text-caos-forest mb-2">Requests & actions ({data.tasks.length})</h3>
        {data.tasks.length === 0 && <div className="text-caos-mute text-sm">None from this conversation.</div>}
        {data.tasks.map((t) => (
          <button
            key={t.task_id}
            onClick={() => setOpenTaskId(t.task_id)}
            className="w-full text-left text-sm py-1 border-b border-caos-line last:border-0 hover:text-caos-forest"
            data-testid={`conversation-task-${t.task_id}`}
          >
            <Badge variant="outline" className="mr-2 uppercase text-[10px]">{t.category}</Badge>
            {t.description} — <span className="text-caos-mute">{t.status}</span>
          </button>
        ))}
      </div>
      {/* Same Communication & Requests detail dialog, same records - not a
          second view of this data. */}
      <RequestDetailDialog taskId={openTaskId} open={!!openTaskId} onOpenChange={(o) => { if (!o) setOpenTaskId(null); }} />

      <div className="mb-4">
        <h3 className="font-display text-lg font-medium text-caos-forest mb-2">Receipts ({data.receipts.length})</h3>
        {data.receipts.length === 0 && <div className="text-caos-mute text-sm">None.</div>}
        {data.receipts.map((r) => (
          <div key={r.receipt_id} className="text-sm py-1 border-b border-caos-line last:border-0">
            {fmtTime(r.created_at)} — {r.action_type}
            <span className="text-caos-mute text-xs ml-2 font-mono">{r.receipt_id}</span>
          </div>
        ))}
      </div>

      {data.device_actions.length > 0 && (
        <div className="mb-4">
          <h3 className="font-display text-lg font-medium text-caos-forest mb-2">Device actions ({data.device_actions.length})</h3>
          <p className="text-caos-mute text-xs mb-2">Best-effort match by room + time window, not tagged to this session at the source.</p>
          {data.device_actions.map((d, i) => (
            <div key={i} className="text-sm py-1 border-b border-caos-line last:border-0">
              {fmtTime(d.issued_at)} — {d.action} → {String(d.value)}
            </div>
          ))}
        </div>
      )}

      {data.diagnostics.length > 0 && (
        <div>
          <h3 className="font-display text-lg font-medium text-caos-forest mb-2">Voice diagnostics ({data.diagnostics.length})</h3>
          <div className="max-h-48 overflow-y-auto text-xs font-mono text-caos-mute space-y-0.5">
            {data.diagnostics.map((e, i) => (
              <div key={i}>
                {fmtTime(e.created_at)} — {e.event_type}
                {e.assistant_speaking != null && ` (aria_speaking=${e.assistant_speaking})`}
                {e.text && ` "${e.text}"`}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
