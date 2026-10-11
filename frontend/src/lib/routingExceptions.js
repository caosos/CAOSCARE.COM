// Routing exceptions (GET /ops/routing-exceptions): wording only; the classes and counts come from the server.
export const CLASS_LABEL = { undelivered: "Not delivered", unassigned: "Unassigned", overdue: "Overdue", failed_handoff: "Failed handoff" };
export const CLASS_ORDER = ["undelivered", "unassigned", "overdue", "failed_handoff"];

export function ageText(sec) {
  if (sec == null) return "";
  if (sec < 3600) return `${Math.max(1, Math.floor(sec / 60))}m`;
  if (sec < 86400) return `${Math.floor(sec / 3600)}h`;
  return `${Math.floor(sec / 86400)}d`;
}

export function latestActionText(a) {
  if (!a) return "";
  const who = a.by_name ? ` by ${a.by_name}` : "";
  const what = { created: `Created${a.text ? ` (${a.text})` : ""}`, assigned_to: a.to ? "Assigned" : "Unassigned", acknowledged: "Acknowledged",
    status: { in_progress: "Started", completed: "Completed", skipped: "Cancelled", pending: "Reopened" }[a.to] || "Status changed",
    note: "Note", scheduled: "Visit window set", re_request: "Asked again" }[a.field] || String(a.field || "").replace(/_/g, " ");
  return `${what}${who}`;
}
