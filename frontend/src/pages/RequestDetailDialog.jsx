import React, { useEffect, useState } from "react";
import { api } from "../lib/api";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "../components/ui/dialog";
import { Button } from "../components/ui/button";
import { Badge } from "../components/ui/badge";
import { toast } from "sonner";
import { sourceLabel, deriveStatus, STATUS_BADGE_CLASS, fmtDateTime } from "../lib/requestDisplay";

function humanizeAction(actionType) {
  const s = (actionType || "").replace(/_/g, " ");
  return s.charAt(0).toUpperCase() + s.slice(1);
}

function buildTimeline(task, receipts) {
  const events = [];
  events.push({ at: task.created_at, label: task.resident_words ? `Requested: "${task.resident_words}"` : "Request created" });
  for (const r of receipts) {
    events.push({ at: r.created_at, label: humanizeAction(r.action_type), meta: r.receipt_id });
  }
  if (task.acknowledged_at) events.push({ at: task.acknowledged_at, label: `Acknowledged${task.acknowledged_by_name ? ` by ${task.acknowledged_by_name}` : ""}` });
  if (task.started_at) events.push({ at: task.started_at, label: `Work started${task.assigned_name ? ` — ${task.assigned_name}` : ""}` });
  if (task.completed_at) {
    events.push({ at: task.completed_at, label: task.status === "skipped" ? "Cancelled" : `Completed${task.completed_by_name ? ` by ${task.completed_by_name}` : ""}` });
  }
  return events.filter((e) => e.at).sort((a, b) => new Date(a.at) - new Date(b.at));
}

export default function RequestDetailDialog({ taskId, open, onOpenChange, onChange }) {
  const [data, setData] = useState(null);

  const load = () => {
    if (!taskId) return;
    api.get(`/tasks/${taskId}/detail`).then(({ data: d }) => setData(d)).catch(() => toast.error("Could not load request"));
  };
  useEffect(() => { if (open) load(); }, [taskId, open]); // eslint-disable-line react-hooks/exhaustive-deps

  const act = async (action) => {
    try {
      await api.post(`/tasks/${taskId}/${action}`);
      toast.success(action.charAt(0).toUpperCase() + action.slice(1) + "d");
      load();
      onChange?.();
    } catch (err) { toast.error(err?.response?.data?.detail || "Failed"); }
  };

  if (!taskId) return null;
  const t = data?.task;
  const ds = t ? deriveStatus(t) : null;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl max-h-[85vh] overflow-y-auto" data-testid="request-detail-dialog">
        <DialogHeader><DialogTitle className="font-display">Request detail</DialogTitle></DialogHeader>
        {!data ? <div className="text-caos-mute text-sm">Loading…</div> : (
          <>
            <div className="grid grid-cols-2 gap-x-4 gap-y-2 text-sm mb-4">
              <div><span className="text-caos-mute">Resident</span><div className="font-semibold text-caos-forest">{t.resident_name || "unknown"}{t.room ? ` (Rm ${t.room})` : ""}</div></div>
              <div><span className="text-caos-mute">Department</span><div className="font-semibold text-caos-forest uppercase text-xs tracking-wider">{t.category}</div></div>
              <div><span className="text-caos-mute">Requested at</span><div>{fmtDateTime(t.created_at)}</div></div>
              <div><span className="text-caos-mute">Requested by / source</span><div>{sourceLabel(t.source)}</div></div>
              <div><span className="text-caos-mute">Priority</span><div className="uppercase text-xs">{t.priority}</div></div>
              <div><span className="text-caos-mute">Status</span><div><Badge className={STATUS_BADGE_CLASS[ds]}>{ds}</Badge></div></div>
              <div><span className="text-caos-mute">Assigned to</span><div>{t.assigned_name || <span className="italic text-caos-mute">unassigned</span>}</div></div>
              {t.requested_for_date && <div><span className="text-caos-mute">Requested for</span><div>{t.requested_for_date} {t.requested_for_time_label && `(${t.requested_for_time_label})`}</div></div>}
              {t.re_request_count > 0 && <div><span className="text-caos-mute">Asked again</span><div>{t.re_request_count}x</div></div>}
              {t.conversation_session_id && <div className="col-span-2"><span className="text-caos-mute">Conversation session</span><div className="font-mono text-xs text-caos-mute">{t.conversation_session_id}</div></div>}
            </div>
            <div className="mb-4">
              <div className="text-caos-mute text-xs uppercase tracking-widest mb-1">Request</div>
              <div className="text-sm">{t.description || t.title}</div>
            </div>

            <div className="flex gap-2 mb-4">
              {!t.acknowledged_at && <Button size="sm" variant="outline" className="border-2" onClick={() => act("acknowledge")} data-testid="request-acknowledge-btn">Acknowledge</Button>}
              {t.status === "pending" && <Button size="sm" className="bg-caos-forest" onClick={() => act("start")} data-testid="request-start-btn">Start</Button>}
              {t.status !== "completed" && t.status !== "skipped" && <Button size="sm" variant="outline" className="border-2" onClick={() => act("complete")} data-testid="request-complete-btn">Complete</Button>}
            </div>

            <div>
              <h3 className="font-display text-lg font-medium text-caos-forest mb-2">Timeline</h3>
              <div className="space-y-1.5 text-sm">
                {buildTimeline(t, data.receipts).map((e, i) => (
                  <div key={i} className="flex gap-3">
                    <span className="text-caos-mute text-xs whitespace-nowrap w-32">{fmtDateTime(e.at)}</span>
                    <span>{e.label}</span>
                  </div>
                ))}
              </div>
            </div>
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}
