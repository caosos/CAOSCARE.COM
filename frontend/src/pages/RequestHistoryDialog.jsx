import React, { useEffect, useState } from "react";
import { api } from "../lib/api";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "../components/ui/dialog";

// Timeline of one department request: the task's own lifecycle timestamps
// plus every receipt filed against it (GET /tasks/{id}/detail).
export default function RequestHistoryDialog({ taskId, onClose }) {
  const [data, setData] = useState(null);
  useEffect(() => {
    if (!taskId) { setData(null); return; }
    api.get(`/tasks/${taskId}/detail`).then(({ data: d }) => setData(d)).catch(() => setData(null));
  }, [taskId]);
  if (!taskId) return null;
  const t = data?.task;
  const events = [];
  if (t) {
    events.push({ at: t.created_at, label: `Created${t.source ? ` (${t.source.replace(/_/g, " ")})` : ""}` });
    (data.receipts || []).forEach((r) => events.push({ at: r.created_at, label: `${r.action_type.replace(/_/g, " ")} · ${r.status}` }));
    if (t.acknowledged_at) events.push({ at: t.acknowledged_at, label: `Acknowledged${t.acknowledged_by_name ? ` by ${t.acknowledged_by_name}` : ""}` });
    if (t.started_at) events.push({ at: t.started_at, label: `Started${t.assigned_name ? ` by ${t.assigned_name}` : ""}` });
    if (t.completed_at) events.push({ at: t.completed_at, label: `Completed${t.completed_by_name ? ` by ${t.completed_by_name}` : ""}${t.duration_minutes ? ` · ${t.duration_minutes} min` : ""}` });
  }
  events.sort((a, b) => new Date(a.at || 0) - new Date(b.at || 0));
  return (
    <Dialog open={!!taskId} onOpenChange={(o) => { if (!o) onClose(); }}>
      <DialogContent className="max-w-lg" data-testid="request-history-dialog">
        <DialogHeader><DialogTitle className="font-display">Request history</DialogTitle></DialogHeader>
        {!t ? <div className="text-caos-mute text-sm">Loading…</div> : (
          <>
            <div className="text-sm font-medium text-caos-forest">{t.title}</div>
            {t.resident_words && <div className="text-sm text-caos-ink/80 mt-1">Resident said: "{t.resident_words}"</div>}
            {t.notes && <div className="text-sm text-caos-ink/80 mt-1">Staff note: {t.notes}</div>}
            <div className="mt-3 space-y-1 text-sm">
              {events.map((e, i) => (
                <div key={i} className="flex gap-3">
                  <span className="text-xs text-caos-mute w-40 shrink-0">{e.at ? new Date(e.at).toLocaleString() : "—"}</span>
                  <span>{e.label}</span>
                </div>
              ))}
            </div>
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}
