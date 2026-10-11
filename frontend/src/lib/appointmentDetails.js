// Optional operational details on a staff request / appointment:
// provider_name, discipline, location (StaffTask fields, set through the
// canonical PATCH /tasks/{id} and receipted as task_details_updated).
// One place for how they are worded to staff and how a form hands them back,
// so the queue card, the Plan dialog and the admin detail dialog cannot drift.

export const DETAIL_FIELDS = ["provider_name", "discipline", "location"];

/** "With: Tess Ortiz PT (physical therapy) · Where: Therapy room" or "" when nothing is set. */
export function detailsLine(t) {
  if (!t) return "";
  const parts = [];
  if (t.provider_name) parts.push(`With: ${t.provider_name}${t.discipline ? ` (${t.discipline})` : ""}`);
  else if (t.discipline) parts.push(`Kind: ${t.discipline}`);
  if (t.location) parts.push(`Where: ${t.location}`);
  return parts.join(" · ");
}

/** Form values -> PATCH body. Trimmed; an empty value is sent as "" so the server clears the field. */
export function detailsPayload({ provider = "", discipline = "", location = "" }) {
  return { provider_name: provider.trim(), discipline: discipline.trim(), location: location.trim() };
}
