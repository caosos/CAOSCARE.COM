export function resetConfirmation(runId) {
  return `RESET ${runId}`;
}

export function resetPayload(run, confirmation) {
  if (!run?.run_id || run?.state !== "STOPPED") {
    throw new Error("An exact stopped run is required");
  }
  return {
    run_id: run.run_id,
    expected_state: "STOPPED",
    confirmation,
    operation_key: `staff-ui:reset:${run.run_id}`,
  };
}

export function resetErrorMessage(error) {
  const detail = error?.response?.data?.detail;
  if (typeof detail === "string") return detail;
  return detail?.message || "Living Community reset was refused";
}
