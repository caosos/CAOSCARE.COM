// Recurring series wording (backend task_recurrence.py). Weekday 0 = Monday.
export const WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];

export function seriesLabel(t) {
  if (!t) return "";
  const when = t.recur === "weekly"
    ? (t.weekday != null ? `Every ${WEEKDAYS[t.weekday]}` : "Weekly (no day set)")
    : "Every day";
  return [when, t.time_label ? `at ${t.time_label}` : null].filter(Boolean).join(" ");
}

export function templatePayload(form) {
  const p = { title: form.title.trim(), description: form.description || "", category: form.department || form.category,
    shift: form.shift, recur: form.recur };
  if (form.recur === "weekly") p.weekday = Number(form.weekday);
  if (form.time_label?.trim()) p.time_label = form.time_label.trim();
  if (form.department) p.department = form.department;
  if (form.resident_id) p.resident_id = form.resident_id;
  for (const k of ["provider_name", "discipline", "location"]) if (form[k]?.trim()) p[k] = form[k].trim();
  return p;
}
