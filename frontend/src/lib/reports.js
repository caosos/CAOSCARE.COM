// Pure helpers for the Operations reports tab. The server (routes/reports.py)
// owns every number and the row order; these only label and tone what it
// returns, and build the CSV request URL for the same filtered query.

export const EXCEPTION_KIND_LABEL = {
  open_assistance_event: "Open assistance event",
  overdue: "Overdue work",
  failed_action: "Failed / cancelled action",
  transportation_attention: "Transportation",
  re_requested_open: "Re-requested, still open",
  unassigned_open: "Unassigned open work",
};

export function exceptionKindLabel(kind) {
  return EXCEPTION_KIND_LABEL[kind] || String(kind || "").replace(/_/g, " ");
}

// "critical" | "warn" | "info" | "stale" - deterministic from the row.
export function exceptionTone(row) {
  if (!row) return "info";
  const r = String(row.reason || "");
  if (row.kind === "open_assistance_event") return /stale test data/.test(r) ? "stale" : "critical";
  if (row.kind === "overdue" || row.kind === "failed_action") return "warn";
  return "info";
}

export function fmtHours(h) {
  const n = Number(h);
  if (!Number.isFinite(n) || n <= 0) return "0h";
  if (n < 1) return `${Math.round(n * 60)}m`;
  if (n < 48) return `${Math.round(n)}h`;
  return `${Math.round(n / 24)}d`;
}

// YYYY-MM-DD, local, `daysBack` days before today (default 6 -> a 7-day window).
export function defaultWeekStart(daysBack = 6, base = new Date()) {
  const d = new Date(base.getTime() - daysBack * 86400_000);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

export function buildQuery(params) {
  const q = new URLSearchParams();
  Object.entries(params || {}).forEach(([k, v]) => {
    if (v !== undefined && v !== null && v !== "" && v !== "all") q.append(k, v);
  });
  return q.toString();
}
