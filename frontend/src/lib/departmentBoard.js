// Department board (GET /departments/{slug}/board): one read over the canonical
// records. These helpers only word what the record says.
export function ago(iso) {
  if (!iso) return "";
  const ms = Date.now() - new Date(iso).getTime();
  const m = Math.floor(ms / 60000);
  if (m < 1) return "just now";
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  return `${Math.floor(h / 24)}d ago`;
}

export const LIFECYCLE_LABEL = { open: "not yet picked up", acknowledged: "taken on", in_progress: "in progress", resolved: "done" };

/** One short line per dispatch step: "claimed by Carl Boone · 2h ago". */
export function trailLine(e) {
  const who = e.by_name ? ` by ${e.by_name}` : "";
  const when = e.at ? ` · ${ago(e.at)}` : "";
  switch (e.field) {
    case "created": return `Created${e.text ? ` (${e.text})` : ""}${when}`;
    case "assigned_to": return e.to ? `Assigned to ${e.to_name || "staff"}${who}${when}` : `Unassigned${who}${when}`;
    case "acknowledged": return `Acknowledged${who}${when}`;
    case "status": return `${{ in_progress: "Started", completed: "Completed", skipped: "Cancelled", pending: "Reopened" }[e.to] || e.to}${who}${when}`;
    case "note": return `Note${who}${when}: ${e.text || ""}`;
    case "scheduled": return `Visit window set${who}${when}: ${e.text || ""}`;
    case "re_request": return `Asked again${when}`;
    default: return `${String(e.field || "").replace(/_/g, " ")}${who}${when}${e.text ? `: ${e.text}` : ""}`;
  }
}

export function workerSummary(group) {
  const n = group.work.length;
  const inProg = group.work.filter((r) => r.status === "in_progress").length;
  if (!n) return "nothing open";
  return `${n} open${inProg ? ` · ${inProg} in progress` : ""}`;
}
