import React from "react";
import { Badge } from "../ui/badge";
import { Button } from "../ui/button";

const titleCase = (value) => String(value || "unknown").replaceAll("_", " ");
const time = (value) => value ? new Date(value).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : "time unknown";

function TaskRow({ task, onOpenRequest }) {
  const person = task.resident?.name || task.resident?.id || "Synthetic resident unknown";
  return (
    <li className="rounded-lg border border-caos-line bg-white p-3" data-testid={`community-task-${task.task_id}`}>
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant="outline" className="text-[10px] uppercase">Simulated</Badge>
            <span className="text-xs font-semibold uppercase tracking-wide text-caos-mute">{titleCase(task.department)}</span>
          </div>
          <p className="mt-1 break-words text-sm font-semibold text-caos-forest">{task.summary || "Summary unavailable"}</p>
          <p className="text-xs text-caos-mute">{person} · {titleCase(task.priority)} priority</p>
          <p className="font-mono text-[11px] text-caos-mute">{task.task_id}</p>
        </div>
        <Badge variant="outline">{titleCase(task.status)}</Badge>
      </div>
      <div className="mt-2 flex flex-wrap items-center justify-between gap-2 text-xs text-caos-mute">
        <span>
          {task.assigned_worker?.name || task.assigned_worker?.id
            ? `Assigned to ${task.assigned_worker.name || task.assigned_worker.id}`
            : "Unassigned"}
          {` · updated ${time(task.updated_at)}`}
        </span>
        {task.task_id && onOpenRequest && (
          <Button type="button" size="sm" variant="outline" onClick={() => onOpenRequest(task.task_id)}>
            Open ticket
          </Button>
        )}
      </div>
    </li>
  );
}

function TransitionRow({ row, onOpenRequest }) {
  const actor = row.actor?.name || row.actor?.id || "Actor unknown";
  const transition = row.before_status || row.after_status
    ? `${titleCase(row.before_status)} → ${titleCase(row.after_status)}`
    : titleCase(row.status);
  return (
    <li className="border-b border-caos-line py-2 last:border-0" data-testid={`community-receipt-${row.receipt_id}`}>
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="text-sm font-semibold text-caos-forest">{titleCase(row.action_type)} · {transition}</p>
          <p className="text-xs text-caos-mute">
            {actor} · {titleCase(row.actor?.type)} · {titleCase(row.actor?.channel || row.source)} · {titleCase(row.authority)} · {time(row.created_at)}
          </p>
          <p className="font-mono text-[11px] text-caos-mute">
            {row.receipt_id} · provenance {row.provenance_status}
          </p>
        </div>
        {row.task_id && onOpenRequest && (
          <Button type="button" size="sm" variant="ghost" onClick={() => onOpenRequest(row.task_id)}>
            Ticket
          </Button>
        )}
      </div>
    </li>
  );
}

function Unknown({ kind }) {
  return (
    <p className="mt-2 text-sm italic text-caos-mute">
      Recent {kind} are unknown. This is not evidence that none exist.
    </p>
  );
}

export default function SimCommunityActivity({ activity, runId, onOpenRequest }) {
  const exact = activity?.run_id && activity.run_id === runId;
  const tasks = exact ? activity.tasks?.items : null;
  const transitions = exact ? activity.transitions?.items : null;
  return (
    <section className="space-y-4 border-t border-caos-line pt-4" aria-labelledby="community-activity-heading">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h3 id="community-activity-heading" className="text-xs font-bold uppercase tracking-widest text-caos-mute">
            Live canonical activity
          </h3>
          <p className="mt-1 text-xs text-caos-mute">Recent exact-run simulated tickets and receipt-backed transitions.</p>
        </div>
        <Badge variant="outline" className={activity?.status === "loaded" ? "text-caos-forest" : "text-caos-terracotta"}>
          {exact ? titleCase(activity.status) : "unknown"}
        </Badge>
      </div>

      <div className="grid gap-4 xl:grid-cols-2">
        <div>
          <h4 className="text-sm font-semibold text-caos-forest">Tickets moving now</h4>
          {tasks === null ? <Unknown kind="tickets" /> : tasks.length === 0 ? (
            <p className="mt-2 text-sm text-caos-mute">This exact run has no canonical tickets yet.</p>
          ) : (
            <ul className="mt-2 max-h-[32rem] space-y-2 overflow-y-auto pr-1" data-testid="community-live-tasks">
              {tasks.map((task) => <TaskRow key={task.task_id} task={task} onOpenRequest={onOpenRequest} />)}
            </ul>
          )}
        </div>
        <div>
          <h4 className="text-sm font-semibold text-caos-forest">Receipt-backed changes</h4>
          {transitions === null ? <Unknown kind="transitions" /> : transitions.length === 0 ? (
            <p className="mt-2 text-sm text-caos-mute">This exact run has no task transition receipts yet.</p>
          ) : (
            <ul className="mt-2 max-h-[32rem] overflow-y-auto rounded-lg border border-caos-line px-3" data-testid="community-live-transitions">
              {transitions.map((row) => <TransitionRow key={row.receipt_id} row={row} onOpenRequest={onOpenRequest} />)}
            </ul>
          )}
        </div>
      </div>
    </section>
  );
}
