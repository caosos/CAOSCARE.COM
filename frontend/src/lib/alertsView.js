// Pure helpers for the Alerts board. The server owns the alert records
// (GET /alerts, GET /alerts/stats); this only classifies and tones them
// for display and applies the honest stale-age distinction - it never
// deletes or rewrites anything.

const STALE_HOURS = 72;
const OPEN = ["active", "acknowledged"];

export function ageHours(iso, now = Date.now()) {
  if (!iso) return 0;
  const t = new Date(iso).getTime();
  return Number.isFinite(t) ? Math.max(0, (now - t) / 3600_000) : 0;
}

// An OPEN alert older than 72h is very likely stale RF/pendant test debris,
// not a live event (see docs/PROJECT_STATE.md 2026-09-06). We flag it,
// never hide the record.
export function isLikelyStale(a, now = Date.now()) {
  return OPEN.includes(a?.status) && ageHours(a?.created_at, now) > STALE_HOURS;
}

export function alertTone(a) {
  if (!a) return "muted";
  if (a.status === "resolved") return "muted";
  if (a.severity === "emergency") return "critical";
  if (a.severity === "assist") return "warn";
  return "info";
}

// Counts for the honesty banner. `open_total` is every active+acknowledged;
// `likely_stale` is the subset over 72h; `live` is the trustworthy remainder.
export function staleSummary(alerts, now = Date.now()) {
  const open = (alerts || []).filter((a) => OPEN.includes(a.status));
  const stale = open.filter((a) => isLikelyStale(a, now));
  return { open_total: open.length, likely_stale: stale.length, live: open.length - stale.length };
}

export function filterAlerts(alerts, { status = "all", severity = "all", hideStale = false } = {}, now = Date.now()) {
  return (alerts || [])
    .filter((a) => status === "all" || a.status === status)
    .filter((a) => severity === "all" || a.severity === severity)
    .filter((a) => !hideStale || !isLikelyStale(a, now))
    .sort((x, y) => new Date(y.created_at || 0) - new Date(x.created_at || 0));
}

export { STALE_HOURS };
