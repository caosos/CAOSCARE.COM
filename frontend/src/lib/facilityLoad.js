// A failed read is an unknown state, never evidence that the facility list is
// empty. Keeping this distinction outside the component makes it difficult for
// a catch/finally path to accidentally turn an error into an empty success.
export async function fetchFacilitySnapshot(apiClient) {
  try {
    const response = await apiClient.get("/facilities");
    if (!Array.isArray(response.data)) throw new Error("Invalid facilities response");
    return { loadState: "ready", facilities: response.data };
  } catch {
    return { loadState: "error", facilities: null };
  }
}
