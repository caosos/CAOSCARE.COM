// Timeline of one request, built from the task's append-only event_log
// (backend/routes/task_history.py). Tasks created before event_log existed
// have no or partial logs; for any step the log does not cover we fall back
// to the task's own timestamp fields, so old requests still show what is
// known and nothing is invented.

const STATUS_LABEL = {
  in_progress: "Started",
  completed: "Completed",
  skipped: "Skipped",
  pending: "Reopened",
};

const by = (e) => (e.by_name ? ` by ${e.by_name}` : "");

function describe(e, task) {
  switch (e.field) {
    case "status": {
      let label = `${STATUS_LABEL[e.to] || `Status: ${String(e.to).replace(/_/g, " ")}`}${by(e)}`;
      if (e.to === "completed" && task.duration_minutes) label += ` · ${task.duration_minutes} min`;
      return { label };
    }
    case "acknowledged":
      return { label: `Acknowledged${by(e)}` };
    case "assigned_to":
      if (!e.to) return { label: `Unassigned${by(e)}` };
      if (e.to === e.by) return { label: `Claimed${by(e)}` };
      return { label: `Assigned to ${e.to_name || "staff"}${by(e)}` };
    case "note":
      return { label: `Note${by(e)}`, text: e.text, kind: "note" };
    case "re_request":
      return { label: `Resident asked again (${Number(e.to) + 1}x)`, text: e.text };
    default: {
      // Domain steps that are not a status change (e.g. a ride booked or
      // changed) carry their detail in `text` - shown as plain detail.
      const name = String(e.field).replace(/_/g, " ");
      return { label: `${name.charAt(0).toUpperCase()}${name.slice(1)}${by(e)}`, text: e.text, kind: "detail" };
    }
  }
}

export function buildRequestTimeline(task) {
  if (!task) return [];
  const log = Array.isArray(task.event_log) ? task.event_log : [];
  const events = [{
    at: task.created_at,
    label: `Created${task.source ? ` (${task.source.replace(/_/g, " ")})` : ""}`,
  }];
  log.forEach((e) => events.push({ at: e.at, ...describe(e, task) }));

  const logged = (pred) => log.some(pred);
  if (task.acknowledged_at && !logged((e) => e.field === "acknowledged")) {
    events.push({ at: task.acknowledged_at, label: `Acknowledged${task.acknowledged_by_name ? ` by ${task.acknowledged_by_name}` : ""}` });
  }
  if (task.started_at && !logged((e) => e.field === "status" && e.to === "in_progress")) {
    events.push({ at: task.started_at, label: `Started${task.assigned_name ? ` by ${task.assigned_name}` : ""}` });
  }
  const closed = ["completed", "skipped"].includes(task.status);
  if (closed && task.completed_at && !logged((e) => e.field === "status" && e.to === task.status)) {
    const who = task.completed_by_name ? ` by ${task.completed_by_name}` : "";
    const mins = task.status === "completed" && task.duration_minutes ? ` · ${task.duration_minutes} min` : "";
    events.push({ at: task.completed_at, label: `${STATUS_LABEL[task.status]}${who}${mins}` });
  }
  return events.sort((a, b) => new Date(a.at || 0) - new Date(b.at || 0));
}

// A note written before note history existed survives only as task.notes.
export function legacyNote(task) {
  if (!task?.notes) return null;
  const hasLoggedNotes = (task.event_log || []).some((e) => e.field === "note");
  return hasLoggedNotes ? null : task.notes;
}
