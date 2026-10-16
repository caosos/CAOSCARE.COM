const ALLOWED_STATUS = new Set(["loaded", "not_started", "unknown", "error"]);
const READINESS_STATUS = new Set(["ready", "not_provisioned", "not_started", "unknown", "error"]);

const nullableCount = (value) => value === null || (Number.isInteger(value) && value >= 0);

export function isCommunityRuntimeSnapshot(value) {
  if (!value || value.schema_version !== 1 || !ALLOWED_STATUS.has(value.status)) return false;
  if (!value.generated_at || value.read_only !== true || !value.run || !value.tickets || !value.staffing) return false;
  if (!ALLOWED_STATUS.has(value.run.status) || !ALLOWED_STATUS.has(value.tickets.status)) return false;
  if (!value.run.resident_readiness
      || !READINESS_STATUS.has(value.run.resident_readiness.status)) return false;
  if (![true, false, null].includes(value.run.resident_readiness.residents_provisioned)) return false;
  if (!ALLOWED_STATUS.has(value.staffing.status) || !value.tickets.counts) return false;
  if (!value.activity || value.activity.read_only !== true || !ALLOWED_STATUS.has(value.activity.status)) return false;
  if (!value.activity.tasks || !value.activity.transitions) return false;
  if (!ALLOWED_STATUS.has(value.activity.tasks.status) || !ALLOWED_STATUS.has(value.activity.transitions.status)) return false;
  if (value.activity.tasks.items !== null && !Array.isArray(value.activity.tasks.items)) return false;
  if (value.activity.transitions.items !== null && !Array.isArray(value.activity.transitions.items)) return false;
  return ["open", "in_progress", "completed", "skipped", "other", "total"]
    .every((key) => nullableCount(value.tickets.counts[key]));
}

export async function fetchCommunityRuntimeSnapshot(apiClient) {
  try {
    const response = await apiClient.get("/simulator/community/runtime");
    if (!isCommunityRuntimeSnapshot(response.data)) throw new Error("Invalid community runtime response");
    return { loadState: "ready", snapshot: response.data };
  } catch {
    return { loadState: "error", snapshot: null };
  }
}

export function communityRuntimeIntro(snapshot) {
  const state = snapshot?.run?.state;
  if (state === "RUNNING" || state === "PAUSED") {
    return "The two runnable scenarios below are legacy demo-room thin slices. The community runtime panel is read-only canonical execution truth for the active living-community run; planned scale remains separate.";
  }
  if (snapshot?.run?.status === "not_started") {
    return "The two runnable scenarios below are demo-room thin slices. The community overview is a planning preview; no living-community run has been started.";
  }
  return "The two runnable scenarios below are demo-room thin slices. Planned community scale and observed runtime truth are shown separately; an unavailable read never proves that execution is stopped.";
}
