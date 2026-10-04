// Pure helpers for the Capacity tab (routes/capacity_monitor.py).

export const LEVEL_TONE = {
  NORMAL: "bg-emerald-100 text-emerald-900",
  WATCH: "bg-amber-100 text-amber-900",
  ACTION_NEEDED: "bg-orange-200 text-orange-950",
  CRITICAL: "bg-red-200 text-red-950",
};

export const LEVEL_LABEL = { NORMAL: "Normal", WATCH: "Watch", ACTION_NEEDED: "Action needed", CRITICAL: "Critical" };

const GROUPS = {
  resident: ["resident_voice", "resident_device", "pendant_help"],
  staff: ["staff_dashboard", "staff_workflow"],
  simulator: ["simulator_resident", "simulator_staff"],
  background: ["background_jobs", "email_notification", "receipt_audit_writes"],
};

// Requests per minute for each load group in one sample, real kept apart
// from simulated.
export function loadGroups(sample) {
  const api = sample?.api || {};
  const perMin = 60 / Math.max(sample?.interval_s || 15, 1);
  const out = {};
  for (const [group, classes] of Object.entries(GROUPS)) {
    out[group] = Math.round(classes.reduce((n, c) => n + ((api[c] || {}).requests || 0), 0) * perMin * 10) / 10;
  }
  return out;
}

export function pct(v) {
  return v === null || v === undefined ? "—" : `${Math.round(v * 10) / 10}%`;
}

export function utilPct(u) {
  return u === null || u === undefined ? "—" : `${Math.round(u * 100)}%`;
}

export function projectionText(p) {
  if (!p) return "No bottleneck measured yet";
  if (p.status === "insufficient_history") return `Not enough history yet (${p.days_of_data} day(s) of data)`;
  if (p.status === "flat_or_falling") return "Usage is flat or falling - no capacity date projected";
  return `At the current trend the bottleneck reaches ${Math.round(p.threshold * 100)}% of its safe value around ${p.projected_date} (${p.days_to_threshold} days)`;
}
