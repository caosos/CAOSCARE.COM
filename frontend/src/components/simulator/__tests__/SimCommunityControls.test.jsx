import React, { act } from "react";
import { createRoot } from "react-dom/client";

jest.mock("@/lib/utils", () => ({ cn: (...values) => values.filter(Boolean).join(" ") }), { virtual: true });
jest.mock("../../../lib/api", () => ({ api: { get: jest.fn(), post: jest.fn() } }));
jest.mock("sonner", () => ({ toast: { success: jest.fn(), error: jest.fn() } }));

import SimCommunityControls from "../SimCommunityControls";
import { api } from "../../../lib/api";
import {
  actionPayload,
  fetchCommunityControlCapability,
  isCommunityControlCapability,
} from "../../../lib/communityControls";


globalThis.IS_REACT_ACT_ENVIRONMENT = true;

const capability = {
  schema_version: 1,
  read_only: true,
  controls_enabled: true,
  mutations_allowed: true,
  transaction_probe: { status: "passed", supported: true, blocker: null },
  index_probe: { status: "passed", ready: true, required: [], blockers: [] },
  available_actions: ["create_paused", "provision_residents", "resume", "pause", "step", "stop"],
  step: { enabled: true, reason: null },
  blockers: [],
};

const run = {
  status: "loaded",
  run_id: "simrun:living:7",
  state: "PAUSED",
  cursor: 12,
  simulated_time: { absolute_minute: 481 },
  resident_readiness: {
    status: "ready", residents_provisioned: true, expected_resident_count: 10,
    receipt_id: "ready-1", reason: null,
  },
};

async function render(props) {
  const element = document.createElement("div");
  const root = createRoot(element);
  await act(async () => root.render(<SimCommunityControls {...props} />));
  await act(async () => Promise.resolve());
  return { element, root };
}

beforeEach(() => {
  jest.clearAllMocks();
});

test("validates the capability and sends exact stable run coordinates", async () => {
  expect(isCommunityControlCapability(capability)).toBe(true);
  expect(actionPayload("resume", run)).toEqual({
    run_id: "simrun:living:7",
    expected_state: "PAUSED",
    expected_cursor: 12,
    expected_sim_minute: 481,
    operation_key: "staff-ui:resume:simrun:living:7:PAUSED:12:481",
  });
  expect(actionPayload("resume", run)).toEqual(actionPayload("resume", run));
  expect(actionPayload("create_paused", null)).toEqual({
    expected_state: "ABSENT", expected_cursor: 0, expected_sim_minute: 0,
    operation_key: "staff-ui:create-paused:living-community-burn-in",
  });
  await expect(fetchCommunityControlCapability({
    get: jest.fn().mockResolvedValue({ data: capability }),
  })).resolves.toEqual({ loadState: "ready", capability });
});

test("labels Living Community separately and explains why default-off actions are disabled", async () => {
  api.get.mockResolvedValue({ data: {
    ...capability,
    controls_enabled: false,
    mutations_allowed: false,
    available_actions: [],
    step: {
      enabled: false,
      reason: "Step requires the same explicit flag, transaction, and index gates.",
    },
    blockers: [{
      code: "controls_not_enabled",
      message: "Set CAOSCARE_LIVING_COMMUNITY_CONTROLS=true explicitly to enable mutations.",
    }],
  } });
  const view = await render({ snapshot: { run }, onRuntimeRefresh: jest.fn() });
  expect(view.element.textContent).toMatch(/Living Community controls.*separate from the legacy demo simulator/i);
  expect(view.element.querySelector("[data-testid=community-control-state]").textContent).toBe("PAUSED");
  expect(view.element.querySelector("[data-testid=community-controls-blockers]").textContent)
    .toMatch(/CAOSCARE_LIVING_COMMUNITY_CONTROLS=true/);
  expect(view.element.querySelector("[data-testid=community-control-resume]").disabled).toBe(true);
  expect(view.element.querySelector("[data-testid=community-control-stop]").disabled).toBe(true);
  expect(view.element.querySelector("[data-testid=community-control-step]").disabled).toBe(true);
  expect(view.element.querySelector("[data-testid=community-step-reason]").textContent)
    .toMatch(/explicit flag, transaction, and index gates/i);
  await act(async () => view.root.unmount());
});

test("resume posts exact PAUSED position then refreshes current runtime truth", async () => {
  api.get.mockResolvedValue({ data: capability });
  api.post.mockResolvedValue({ data: { ok: true } });
  const refreshed = jest.fn().mockResolvedValue(undefined);
  const view = await render({ snapshot: { run }, onRuntimeRefresh: refreshed });
  await act(async () => view.element.querySelector("[data-testid=community-control-resume]").click());
  expect(api.post).toHaveBeenCalledWith(
    "/simulator/community/controls/resume",
    actionPayload("resume", run),
  );
  expect(refreshed).toHaveBeenCalledTimes(1);
  await act(async () => view.root.unmount());
});

test("manual step posts one exact PAUSED position under the verified gate", async () => {
  api.get.mockResolvedValue({ data: capability });
  api.post.mockResolvedValue({ data: { ok: true } });
  const refreshed = jest.fn().mockResolvedValue(undefined);
  const view = await render({ snapshot: { run }, onRuntimeRefresh: refreshed });
  const step = view.element.querySelector("[data-testid=community-control-step]");
  expect(step.disabled).toBe(false);
  await act(async () => step.click());
  expect(api.post).toHaveBeenCalledWith(
    "/simulator/community/controls/step",
    actionPayload("step", run),
  );
  expect(refreshed).toHaveBeenCalledTimes(1);
  await act(async () => view.root.unmount());
});

test("paused unprovisioned run offers provisioning and keeps resume disabled", async () => {
  api.get.mockResolvedValue({ data: capability });
  api.post.mockResolvedValue({ data: { ok: true } });
  const unprovisioned = {
    ...run,
    resident_readiness: {
      status: "not_provisioned", residents_provisioned: false,
      expected_resident_count: 10, receipt_id: null, reason: null,
    },
  };
  const view = await render({ snapshot: { run: unprovisioned }, onRuntimeRefresh: jest.fn() });
  const provision = view.element.querySelector("[data-testid=community-control-provision_residents]");
  expect(provision).not.toBeNull();
  expect(provision.disabled).toBe(false);
  expect(view.element.querySelector("[data-testid=community-control-resume]").disabled).toBe(true);
  expect(view.element.querySelector("[data-testid=community-control-step]").disabled).toBe(true);
  expect(view.element.querySelector("[data-testid=community-resident-readiness]").textContent)
    .toMatch(/provision the ten simulated.*resume stays disabled/i);
  await act(async () => provision.click());
  expect(api.post).toHaveBeenCalledWith(
    "/simulator/community/controls/provision-residents",
    actionPayload("provision_residents", unprovisioned),
  );
  await act(async () => view.root.unmount());
});

test("unknown resident readiness never enables resume or invents a provisioning need", async () => {
  api.get.mockResolvedValue({ data: capability });
  const unknown = {
    ...run,
    resident_readiness: {
      status: "error", residents_provisioned: null,
      expected_resident_count: 10, receipt_id: null, reason: "read_failed",
    },
  };
  const view = await render({ snapshot: { run: unknown }, onRuntimeRefresh: jest.fn() });
  expect(view.element.querySelector("[data-testid=community-control-provision_residents]")).toBeNull();
  expect(view.element.querySelector("[data-testid=community-control-resume]").disabled).toBe(true);
  expect(view.element.querySelector("[data-testid=community-control-step]").disabled).toBe(true);
  expect(view.element.querySelector("[data-testid=community-resident-readiness]").textContent)
    .toMatch(/unknown or invalid/i);
  await act(async () => view.root.unmount());
});

test.each([
  ["RUNNING", "community-control-pause"],
  ["STOPPED", null],
])("shows exact %s state and only its valid actions", async (state, expectedAction) => {
  api.get.mockResolvedValue({ data: capability });
  const view = await render({ snapshot: { run: { ...run, state } }, onRuntimeRefresh: jest.fn() });
  expect(view.element.querySelector("[data-testid=community-control-state]").textContent).toBe(state);
  expect(Boolean(view.element.querySelector("[data-testid=community-control-pause]")))
    .toBe(expectedAction === "community-control-pause");
  if (state === "STOPPED") {
    expect(view.element.textContent).toMatch(/history and receipts remain available/i);
    // A new run can be created beside the stopped one.
    expect(view.element.querySelector("[data-testid=community-control-create_paused]")).not.toBeNull();
  }
  await act(async () => view.root.unmount());
});
