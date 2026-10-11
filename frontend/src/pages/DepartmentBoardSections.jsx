import React from "react";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import { Hand, Play, Check, History } from "lucide-react";
import { ago, trailLine, workerSummary, LIFECYCLE_LABEL } from "../lib/departmentBoard";
import { deliveryTone, showDelivery } from "../lib/requestDelivery";

const STATUS_STYLES = {
  pending: "bg-caos-mute/10 text-caos-mute",
  in_progress: "bg-caos-amber/15 text-[#8B5A20] border border-caos-amber",
  completed: "bg-caos-moss/15 text-caos-forest border border-caos-moss",
  skipped: "bg-caos-line text-caos-mute line-through",
};

export function MembersSection({ members }) {
  return (
    <section className="mt-4" data-testid="dept-members">
      <h3 className="text-sm font-semibold text-caos-forest uppercase tracking-wide mb-2">Members &amp; roles</h3>
      {members.length === 0 && <p className="text-caos-mute text-sm italic">No staff are assigned to this department yet. Add them under Users &amp; access (department field).</p>}
      <div className="flex flex-wrap gap-2">
        {members.map((m) => (
          <span key={m.user_id} className="rounded-full border border-caos-line px-3 py-1 text-sm" data-testid={`dept-member-${m.user_id}`}>
            {m.name} <span className="text-caos-mute">· {m.role === "front_desk" ? "front desk" : m.role}</span>
          </span>
        ))}
      </div>
    </section>
  );
}

function WorkCard({ r, roster, canAssign, me, actions, onHistory }) {
  return (
    <div className="border border-caos-line rounded-lg p-3" data-testid={`dept-workspace-task-${r.task_id}`}>
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="font-medium text-sm break-words">{r.what || r.title}</div>
          {(r.resident_name || r.room) && <div className="text-xs text-caos-mute mt-0.5">{r.resident_name}{r.resident_name && r.room ? " · " : ""}{r.room ? `Room ${r.room}` : ""}</div>}
        </div>
        <Badge className={STATUS_STYLES[r.status] || ""} variant="outline" data-testid={`dept-status-${r.task_id}`}>{LIFECYCLE_LABEL[r.lifecycle] || r.status}</Badge>
      </div>
      {showDelivery(r.delivery) && (
        <div className={`text-xs mt-1 ${deliveryTone(r.delivery) === "warn" ? "text-caos-terracotta font-semibold" : "text-caos-mute"}`} data-testid={`dept-delivery-${r.task_id}`}>{r.delivery.label}</div>
      )}
      <ol className="mt-2 space-y-0.5 text-xs text-caos-mute" data-testid={`dept-trail-${r.task_id}`}>
        {r.trail.map((e, i) => <li key={i}>{trailLine(e)}</li>)}
      </ol>
      {canAssign && (
        <div className="flex flex-wrap items-center gap-1.5 mt-2">
          {!r.acknowledged_at && <Button size="sm" variant="outline" className="border-2 h-7 text-xs" onClick={() => actions.acknowledge(r.task_id)} data-testid={`dept-ack-${r.task_id}`}>Acknowledge</Button>}
          {!r.assigned_to && me && <Button size="sm" variant="outline" className="border-2 h-7 text-xs" onClick={() => actions.assign(r.task_id, me)} data-testid={`dept-claim-${r.task_id}`}><Hand className="w-3.5 h-3.5 mr-1" /> Claim</Button>}
          {r.status === "pending" && <Button size="sm" className="bg-caos-forest hover:bg-caos-forest-hover h-7 text-xs" onClick={() => actions.start(r.task_id)} data-testid={`dept-start-${r.task_id}`}><Play className="w-3.5 h-3.5 mr-1" /> Start</Button>}
          <Button size="sm" variant="outline" className="border-2 h-7 text-xs" onClick={() => actions.complete(r.task_id)} data-testid={`dept-complete-${r.task_id}`}><Check className="w-3.5 h-3.5 mr-1" /> Complete</Button>
          <Select value={r.assigned_to || "__none"} onValueChange={(v) => actions.assign(r.task_id, v === "__none" ? "" : v)}>
            <SelectTrigger className="h-7 w-44 text-xs" data-testid={`dept-assign-${r.task_id}`}><SelectValue placeholder="Assign to…" /></SelectTrigger>
            <SelectContent>
              <SelectItem value="__none">Unassigned</SelectItem>
              {roster.map((u) => <SelectItem key={u.user_id} value={u.user_id}>{u.name}</SelectItem>)}
            </SelectContent>
          </Select>
          <Button size="sm" variant="ghost" className="h-7 text-xs" onClick={() => onHistory(r.task_id)} data-testid={`dept-history-${r.task_id}`}><History className="w-3.5 h-3.5 mr-1" /> Receipts</Button>
        </div>
      )}
    </div>
  );
}

export function WorkByWorkerSection({ byWorker, members, canAssign, me, actions, onHistory }) {
  return (
    <section className="mt-5" data-testid="dept-work">
      <h3 className="text-sm font-semibold text-caos-forest uppercase tracking-wide mb-2">Open work by worker</h3>
      {byWorker.every((g) => g.work.length === 0) && <p className="text-caos-mute text-sm italic py-2">Nothing open routed to this department right now.</p>}
      {byWorker.map((g) => (
        <div key={g.user_id || "unassigned"} className="mb-3" data-testid={`dept-worker-${g.user_id || "unassigned"}`}>
          <div className="text-sm font-medium flex items-baseline gap-2">
            <span>{g.name}{g.not_member ? <span className="text-caos-mute text-xs"> (not a member)</span> : null}</span>
            <span className="text-xs text-caos-mute" data-testid={`dept-worker-summary-${g.user_id || "unassigned"}`}>{workerSummary(g)}</span>
          </div>
          <div className="space-y-2 mt-1">
            {g.work.map((r) => <WorkCard key={r.task_id} r={r} roster={members} canAssign={canAssign} me={me} actions={actions} onHistory={onHistory} />)}
          </div>
        </div>
      ))}
    </section>
  );
}

export function CompletedSection({ history, onHistory }) {
  return (
    <section className="mt-5" data-testid="dept-history">
      <h3 className="text-sm font-semibold text-caos-forest uppercase tracking-wide mb-2">Completed &amp; closed (latest {history.length})</h3>
      {history.length === 0 && <p className="text-caos-mute text-sm italic">Nothing completed yet.</p>}
      <div className="space-y-2">
        {history.map((r) => (
          <div key={r.task_id} className="border border-caos-line rounded-lg p-3 text-sm" data-testid={`dept-done-${r.task_id}`}>
            <div className="flex items-start justify-between gap-2">
              <div className="min-w-0 break-words">{r.what || r.title}{r.resident_name ? <span className="text-caos-mute"> · {r.resident_name}</span> : null}</div>
              <Badge className={STATUS_STYLES[r.status] || ""} variant="outline">{r.status === "skipped" ? "cancelled" : "completed"}</Badge>
            </div>
            <div className="text-xs text-caos-mute mt-1">
              {r.status === "completed" ? "Completed" : "Closed"}{r.completed_by_name ? ` by ${r.completed_by_name}` : ""}{r.completed_at ? ` · ${ago(r.completed_at)}` : ""}
              {r.duration_minutes != null ? ` · ${r.duration_minutes} min` : ""} · {r.receipts_count} receipt{r.receipts_count === 1 ? "" : "s"}
            </div>
            {r.notes && <div className="text-xs text-caos-ink/80 mt-1">Note: {r.notes}</div>}
            <Button size="sm" variant="ghost" className="h-7 text-xs mt-1 px-0" onClick={() => onHistory(r.task_id)} data-testid={`dept-done-history-${r.task_id}`}><History className="w-3.5 h-3.5 mr-1" /> Full history &amp; receipts</Button>
          </div>
        ))}
      </div>
    </section>
  );
}
