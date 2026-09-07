// Pure presentational helpers for the Admin/ED operations overview.
// Kept out of the component so the age/accent/link mapping is unit-testable
// without a DOM. The server (routes/ops_overview.py) owns all ranking and
// counting; this file only formats what it returns.

export function formatAge(seconds) {
  const s = Math.max(0, Math.floor(Number(seconds) || 0));
  if (s < 60) return "just now";
  if (s < 3600) return `${Math.floor(s / 60)}m`;
  if (s < 86400) return `${Math.floor(s / 3600)}h`;
  return `${Math.floor(s / 86400)}d`;
}

// One of "critical" | "warn" | "info" | "stale", used to pick a row accent.
// Deterministic from tier + severity so the same payload always renders the
// same way.
export function attentionAccent(item) {
  if (!item) return "info";
  if (item.tier >= 7) return "stale";
  if (item.tier === 0 || item.severity === "emergency") return "critical";
  if (item.tier <= 3) return "warn";
  return "info";
}

const ACCENT_STYLE = {
  critical: { border: "#B6463A", bg: "#FDECE9", text: "#98392F" },
  warn: { border: "#D28D38", bg: "#FDF3E3", text: "#8B5A20" },
  info: { border: "#4A7C59", bg: "#EAF3EC", text: "#2F5940" },
  stale: { border: "#A8A29E", bg: "#F3F1EE", text: "#7A6B56" },
};

export function accentStyle(accent) {
  return ACCENT_STYLE[accent] || ACCENT_STYLE.info;
}

// Where an attention row / task row should send the admin. "assistance"
// items live on the staff alert board (a route); everything else is an
// Admin tab the overview can switch to in place.
export function linkTarget(linkHint) {
  if (linkHint === "assistance") return { type: "route", value: "/staff" };
  if (linkHint === "requests") return { type: "tab", value: "requests" };
  if (linkHint === "transportation") return { type: "tab", value: "transportation" };
  return { type: "tab", value: "tasks" };
}

// Compact one-line reason for a department status row, or null if it's clean.
export function departmentAlert(row) {
  if (!row) return null;
  if (row.overdue > 0) return `${row.overdue} overdue`;
  if (row.unassigned > 0) return `${row.unassigned} unassigned`;
  return null;
}
