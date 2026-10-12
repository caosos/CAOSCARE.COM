// Wording for owner/admin inspection of completed work (backend task_review.inspect).
export function inspectionText(t) {
  if (t.inspection_result === "passed") return `Inspected: passed${t.inspected_by_name ? ` (${t.inspected_by_name})` : ""}`;
  if (t.inspection_result === "returned" && t.status !== "completed") return `Returned after inspection: ${t.inspection_note || ""}`;
  return null;
}
