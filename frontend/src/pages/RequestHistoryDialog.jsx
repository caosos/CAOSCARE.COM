import React, { useEffect, useState } from "react";
import { api } from "../lib/api";
import { legacyNote } from "../lib/requestHistory";
import RequestTimeline from "../components/RequestTimeline";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "../components/ui/dialog";

// History of one department request (GET /tasks/{id}/detail).
export default function RequestHistoryDialog({ taskId, onClose }) {
  const [data, setData] = useState(null);
  useEffect(() => {
    if (!taskId) { setData(null); return; }
    api.get(`/tasks/${taskId}/detail`).then(({ data: d }) => setData(d)).catch(() => setData(null));
  }, [taskId]);
  if (!taskId) return null;
  const t = data?.task;
  const oldNote = legacyNote(t);
  return (
    <Dialog open={!!taskId} onOpenChange={(o) => { if (!o) onClose(); }}>
      <DialogContent className="max-w-lg" data-testid="request-history-dialog">
        <DialogHeader><DialogTitle className="font-display">Request history</DialogTitle></DialogHeader>
        {!t ? <div className="text-caos-mute text-sm">Loading…</div> : (
          <>
            <div className="text-sm font-medium text-caos-forest">{t.title}</div>
            {t.resident_words && <div className="text-sm text-caos-ink/80 mt-1">Resident said: "{t.resident_words}"</div>}
            {oldNote && <div className="text-sm text-caos-ink/80 mt-1">Staff note: {oldNote}</div>}
            <div className="mt-3"><RequestTimeline task={t} receipts={data.receipts} /></div>
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}
