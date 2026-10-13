import React, { act } from "react";
import { createRoot } from "react-dom/client";

jest.mock("@/lib/utils", () => ({ cn: (...values) => values.filter(Boolean).join(" ") }), { virtual: true });

import SimCommunityObserved from "../SimCommunityObserved";
import { fetchCommunityObservedSnapshot } from "../../../lib/communityObservedLoad";

globalThis.IS_REACT_ACT_ENVIRONMENT = true;

const snapshot = {
  schema_version: 1,
  status: "loaded",
  observed_at: "2026-10-13T15:00:00+00:00",
  community_id: "sim:community:living-80-v1",
  counts: { residents: 0, tasks: 0, notifications: 0, runs: 0 },
  provisioning: {
    state: "not_provisioned", expected_residents: 10, observed_residents: 0,
    exact_blueprint_residents: 0, missing_count: 10, collision_count: 0,
  },
  marker_anomalies: [],
};

async function render(props) {
  const element = document.createElement("div");
  const root = createRoot(element);
  await act(async () => root.render(<SimCommunityObserved onRetry={() => {}} {...props} />));
  return { element, root };
}

test("loader accepts verified zero and rejects malformed or failed reads", async () => {
  const ready = await fetchCommunityObservedSnapshot({ get: jest.fn().mockResolvedValue({ data: snapshot }) });
  const malformed = await fetchCommunityObservedSnapshot({ get: jest.fn().mockResolvedValue({ data: { counts: {} } }) });
  const failed = await fetchCommunityObservedSnapshot({ get: jest.fn().mockRejectedValue(new Error("down")) });
  expect(ready).toEqual({ loadState: "ready", snapshot });
  expect(malformed).toEqual({ loadState: "error", snapshot: null });
  expect(failed).toEqual({ loadState: "error", snapshot: null });
});

test("loading and initial failure never claim zero or not provisioned", async () => {
  let view = await render({ loadState: "loading", snapshot: null });
  expect(view.element.textContent).toMatch(/Verifying canonical database records/);
  expect(view.element.textContent).not.toMatch(/not provisioned|Residents0/);
  await act(async () => view.root.unmount());

  view = await render({ loadState: "error", snapshot: null });
  expect(view.element.textContent).toMatch(/Observed state unknown/);
  expect(view.element.textContent).toMatch(/does not mean zero residents/);
  await act(async () => view.root.unmount());
});

test("successful zero is explicit and stale refresh preserves last verified counts", async () => {
  const { element, root } = await render({ loadState: "error", snapshot, refreshFailed: true });
  expect(element.textContent).toMatch(/not provisioned/);
  expect(element.textContent).toMatch(/Residents0.*Tasks0.*Notifications0.*Runs0/);
  expect(element.querySelector("[data-testid=sim-observed-stale]").textContent).toMatch(/preserved.*not replaced with zero/);
  await act(async () => root.unmount());
});
