// Shared display helpers for Communication & Requests (RequestsBoard +
// RequestDetailDialog) - one source of truth so the list and detail view
// never disagree about what a status/source label means.

export const SOURCE_LABELS = {
  aria_voice: "Aria voice",
  kiosk_button: "Kiosk button",
  family: "Family",
  front_desk: "Front Desk",
  system: "System/automation",
  staff: "Staff",
};

export function sourceLabel(source) {
  return SOURCE_LABELS[source] || source || "unknown";
}

// Derived DISPLAY status only - never stored, never a new source of truth.
// StaffTask.status itself only has 4 real values (pending/in_progress/
// completed/skipped); this reads the other real fields already on the
// record (acknowledged_at, assigned_to, transport_run_id) to show the
// actual domain state instead of a bare "Pending" that hides it.
export function deriveStatus(t) {
  if (t.status === "completed") return "Completed";
  if (t.status === "skipped") return "Cancelled";
  if (t.category === "transportation") {
    if (t.transport_run_id || t.transport_slot_id) return "Confirmed";
    if (t.status === "in_progress") return "In progress";
    return "Needs coordination";
  }
  if (t.status === "in_progress") return "In progress";
  if (t.assigned_to) return "Assigned";
  if (t.acknowledged_at) return "Acknowledged";
  return "Pending";
}

export const STATUS_BADGE_CLASS = {
  Completed: "bg-caos-line text-caos-mute",
  Cancelled: "bg-caos-line text-caos-mute line-through",
  Confirmed: "bg-caos-forest text-white",
  "In progress": "bg-caos-amber/15 text-[#8B5A20] border border-caos-amber",
  Assigned: "bg-caos-forest/10 text-caos-forest border border-caos-forest",
  Acknowledged: "bg-caos-forest/10 text-caos-forest border border-caos-forest",
  "Needs coordination": "bg-caos-amber/20 text-caos-forest border border-caos-amber",
  Pending: "bg-caos-mute/10 text-caos-mute",
};

export function fmtDateTime(iso) {
  if (!iso) return "—";
  try { return new Date(iso).toLocaleString(undefined, { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" }); }
  catch { return iso; }
}
