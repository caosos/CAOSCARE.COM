// Pure presentational helpers for the Activity log (operational receipts +
// telemetry events browser). The server owns all filtering and ordering
// (GET /receipts, GET /events); these functions only shape a row for
// display and decide where a "open the underlying object" link should go.

export function humanizeAction(s) {
  const txt = String(s || "").replace(/[._]/g, " ").trim();
  return txt ? txt.charAt(0).toUpperCase() + txt.slice(1) : "—";
}

const RECEIPT_TONE = {
  completed: "ok",
  acknowledged: "info",
  in_progress: "info",
  created: "muted",
  failed: "bad",
  cancelled: "muted",
};
export function receiptStatusTone(status) {
  return RECEIPT_TONE[status] || "muted";
}

// Event.status is free text (command_sent, command_verified, ok, error,
// failed, navigated, discovered, configured, …) - bucket by keyword.
export function eventStatusTone(status) {
  const s = String(status || "").toLowerCase();
  if (!s) return "muted";
  if (/(fail|error)/.test(s)) return "bad";
  if (/(verified|ok|success|configured|complete)/.test(s)) return "ok";
  return "info";
}

export function fmtDuration(ms) {
  const n = Number(ms);
  if (!Number.isFinite(n) || n <= 0) return "";
  if (n < 1000) return `${Math.round(n)}ms`;
  if (n < 60000) return `${(n / 1000).toFixed(1)}s`;
  return `${Math.round(n / 60000)}m`;
}

// Where "open the underlying object" should navigate from a receipt. Admin
// tabs get switched in place; an alert opens the staff alert board.
export function receiptLink(receipt) {
  const t = receipt?.related_object_type;
  if (t === "alert") return { type: "route", value: "/staff" };
  if (t === "device_command") return { type: "tab", value: "devices" };
  if (t === "task") {
    const src = receipt?.source || "staff";
    return { type: "tab", value: src === "staff" ? "tasks" : "requests" };
  }
  return null;
}

// One-line preview of an event's metadata blob for a table cell.
export function summarizeMetadata(meta) {
  if (!meta || typeof meta !== "object") return "";
  for (const k of ["message", "text", "summary", "prompt", "utterance", "query", "reason"]) {
    if (typeof meta[k] === "string" && meta[k].trim()) {
      const v = meta[k].trim();
      return v.length > 120 ? `${v.slice(0, 117)}…` : v;
    }
  }
  const keys = Object.keys(meta);
  return keys.length ? `${keys.length} field${keys.length === 1 ? "" : "s"}: ${keys.slice(0, 4).join(", ")}` : "";
}

// Distinct values from a list for populating a filter <select>, sorted,
// blanks dropped.
export function distinct(rows, field) {
  return Array.from(new Set((rows || []).map((r) => r?.[field]).filter(Boolean))).sort();
}
