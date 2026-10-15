// The server's own reason for refusing an action, never a bare "Could not …".
// Handles detail as a string, as {message}, or as a FastAPI validation list.
export function apiErrorText(err, fallback = "The request was refused.") {
  const detail = err?.response?.data?.detail;
  if (typeof detail === "string" && detail.trim()) return detail;
  if (detail && typeof detail.message === "string") return detail.message;
  if (Array.isArray(detail) && detail.length) {
    return detail.map((d) => d?.msg || String(d)).join("; ");
  }
  if (!err?.response) return "The server could not be reached. Check the connection and try again.";
  return `${fallback} (HTTP ${err.response.status})`;
}
