const ACTION_PATHS = {
  create_paused: "create-paused",
  provision_residents: "provision-residents",
  resume: "resume",
  pause: "pause",
  stop: "stop",
  step: "step",
};

export function isCommunityControlCapability(value) {
  return Boolean(
    value
      && value.schema_version === 1
      && value.read_only === true
      && typeof value.controls_enabled === "boolean"
      && typeof value.mutations_allowed === "boolean"
      && Array.isArray(value.available_actions)
      && Array.isArray(value.blockers)
      && value.transaction_probe
      && typeof value.transaction_probe.supported === "boolean"
      && value.index_probe
      && typeof value.index_probe.ready === "boolean"
      && value.step
      && value.step.enabled === false,
  );
}

export async function fetchCommunityControlCapability(apiClient) {
  try {
    const response = await apiClient.get("/simulator/community/controls/capability");
    if (!isCommunityControlCapability(response.data)) throw new Error("Invalid control capability");
    return { loadState: "ready", capability: response.data };
  } catch {
    return { loadState: "error", capability: null };
  }
}

export function operationKey(action, run) {
  if (action === "create_paused") return "staff-ui:create-paused:living-community-burn-in";
  return [
    "staff-ui", action, run?.run_id, run?.state, run?.cursor, run?.simulated_time?.absolute_minute,
  ].join(":");
}

export function actionPayload(action, run) {
  if (action === "create_paused") {
    return {
      expected_state: "ABSENT",
      expected_cursor: 0,
      expected_sim_minute: 0,
      operation_key: operationKey(action, run),
    };
  }
  const minute = run?.simulated_time?.absolute_minute;
  if (!run?.run_id || !["RUNNING", "PAUSED"].includes(run?.state)
      || !Number.isInteger(run?.cursor) || !Number.isInteger(minute)) {
    throw new Error("Exact run state, cursor, and simulated time are required");
  }
  return {
    run_id: run.run_id,
    expected_state: run.state,
    expected_cursor: run.cursor,
    expected_sim_minute: minute,
    operation_key: operationKey(action, run),
  };
}

export async function sendCommunityControl(apiClient, action, run) {
  const path = ACTION_PATHS[action];
  if (!path) throw new Error("Unknown Living Community action");
  return apiClient.post(`/simulator/community/controls/${path}`, actionPayload(action, run));
}

export function controlErrorMessage(error, fallback) {
  const detail = error?.response?.data?.detail;
  if (typeof detail === "string") return detail;
  return detail?.message || fallback;
}
