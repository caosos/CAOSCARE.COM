const validCount = (value) => Number.isInteger(value) && value >= 0;

export function isCommunityObservedSnapshot(value) {
  if (!value || value.schema_version !== 1 || value.status !== "loaded") return false;
  if (!value.observed_at || !value.community_id || !value.counts) return false;
  if (!["residents", "tasks", "notifications", "runs"].every((key) => validCount(value.counts[key]))) {
    return false;
  }
  return Boolean(value.provisioning && [
    "not_provisioned", "partial", "provisioned", "inconsistent",
  ].includes(value.provisioning.state));
}

export async function fetchCommunityObservedSnapshot(apiClient) {
  try {
    const response = await apiClient.get("/simulator/community/observed");
    if (!isCommunityObservedSnapshot(response.data)) throw new Error("Invalid observed community response");
    return { loadState: "ready", snapshot: response.data };
  } catch {
    return { loadState: "error", snapshot: null };
  }
}
