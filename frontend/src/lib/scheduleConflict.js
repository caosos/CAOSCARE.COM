// Planned-window conflicts (GET /tasks/{id}/conflicts, PATCH 409 schedule_conflict).
// Wording and the save-anyway payload live here so the queue's Plan dialog, the
// request detail dialog and the Upcoming view say the same thing.

export function conflictDetail(err) {
  const d = err?.response?.data?.detail;
  return err?.response?.status === 409 && d && d.code === "schedule_conflict" ? d : null;
}

export function describeConflict(c) {
  const base = `${c.what || c.task_id} (${c.category || "request"}) at ${c.requested_for_time_label || "a time not set"}`;
  // Another resident's work with the same provider / staff member: say what is shared.
  return c.kind === "staff" ? `${base}${c.room ? `, room ${c.room}` : ""} — same ${c.shared || "staff"}` : base;
}

/** One line for a conflict result: overlaps, or why it could not be checked, or "" when clear. */
export function conflictSummary(chk) {
  if (!chk) return "";
  if (!chk.checked) return chk.reason ? `Overlap not checked: ${chk.reason}.` : "";
  if (chk.conflicts?.length) return `Overlaps ${chk.conflicts.map(describeConflict).join("; ")}.`;
  if (chk.undetermined?.length) return `No overlap with timed work; ${chk.undetermined.length} other request${chk.undetermined.length > 1 ? "s" : ""} that day has no readable time.`;
  return "";
}

/** Fields to send when staff chose to save despite the overlap. */
export function overridePayload(fields) {
  return { ...fields, conflict_override: true };
}
