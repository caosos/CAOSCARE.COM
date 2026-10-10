import React, { useCallback, useEffect, useRef, useState } from "react";
import { latestOnly } from "../lib/latestOnly";
import { api } from "../lib/api";
import { legacyNote } from "../lib/requestHistory";
import RequestTimeline from "../components/RequestTimeline";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "../components/ui/dialog";

// History of one department request (GET /tasks/{id}/detail).
export default function RequestHistoryDialog({ taskId, onClose }) {
  const [data, setData] = useState(null);
  const [failed, setFailed] = useState(false);
  const guard = useRef(latestOnly());
  const load = useCallback(() => {
    const g = guard.current; const mine = g.next();
    setData(null); setFailed(false);
    if (!taskId) return;
    api.get(`/tasks/${taskId}/detail`)
      .then(({ data: d }) => { if (g.isCurrent(mine)) setData(d); })       // a slower reply for another request is ignored
      .catch(() => { if (g.isCurrent(mine)) setFailed(true); });            // 403/404/network: show a recoverable error, not "Loading"
  }, [taskId]);
  useEffect(() => { const g = guard.current; load(); return () => g.invalidate(); }, [load]);
  if (!taskId) return null;
  const t = data?.task;
  const oldNote = legacyNote(t);
  return (
    <Dialog open={!!taskId} onOpenChange={(o) => { if (!o) onClose(); }}>
      <DialogContent className="max-w-lg" data-testid="request-history-dialog">
        <DialogHeader><DialogTitle className="font-display">Request history</DialogTitle></DialogHeader>
        {failed ? (
          <div className="text-sm" data-testid="request-history-error">
            <span className="text-caos-terracotta">Could not load this request's history.</span>{" "}
            <button className="underline" onClick={load} data-testid="request-history-retry">Try again</button>
          </div>
        ) : !t ? <div className="text-caos-mute text-sm">Loading…</div> : (
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
