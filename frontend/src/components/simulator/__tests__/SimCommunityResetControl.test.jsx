import React, { act } from "react";
import { createRoot } from "react-dom/client";

jest.mock("@/lib/utils", () => ({ cn: (...values) => values.filter(Boolean).join(" ") }), { virtual: true });
jest.mock("../../../lib/api", () => ({ api: { get: jest.fn(), post: jest.fn() } }));
jest.mock("sonner", () => ({ toast: { success: jest.fn(), error: jest.fn() } }));

import SimCommunityResetControl from "../SimCommunityResetControl";
import { api } from "../../../lib/api";
import { resetConfirmation, resetPayload } from "../../../lib/communityResetControl";


globalThis.IS_REACT_ACT_ENVIRONMENT = true;

const capability = {
  schema_version: 1,
  read_only: true,
  controls_enabled: true,
  mutations_allowed: true,
  transaction_probe: { status: "passed", supported: true, blocker: null },
  index_probe: { status: "passed", ready: true, required: [], blockers: [] },
  available_actions: ["create_paused", "resume", "pause", "stop"],
  step: { enabled: false, reason: "exclusive step unavailable" },
  blockers: [],
};
const run = { run_id: "simrun:living:reset-ui", state: "STOPPED" };


async function render(snapshot = { run }) {
  const element = document.createElement("div");
  const root = createRoot(element);
  const refresh = jest.fn().mockResolvedValue(undefined);
  await act(async () => root.render(
    <SimCommunityResetControl snapshot={snapshot} onRuntimeRefresh={refresh} />,
  ));
  await act(async () => Promise.resolve());
  return { element, root, refresh };
}


beforeEach(() => {
  jest.clearAllMocks();
  api.get.mockResolvedValue({ data: capability });
  api.post.mockResolvedValue({ data: { ok: true } });
});


test("is visible only for the exact stopped run and states the preservation boundary", async () => {
  const running = await render({ run: { ...run, state: "RUNNING" } });
  expect(running.element.querySelector("[data-testid=community-reset-control]")).toBeNull();
  await act(async () => running.root.unmount());

  const stopped = await render();
  expect(stopped.element.textContent).toMatch(/only this run's generated community state/i);
  expect(stopped.element.textContent).toMatch(/never runs automatically/i);
  expect(stopped.element.textContent).toMatch(/Historical receipts, real residents, and unrelated simulator runs are preserved/i);
  expect(stopped.element.querySelector("[data-testid=community-reset-submit]").disabled).toBe(true);
  await act(async () => stopped.root.unmount());
});


test("requires typed run id confirmation and submits a stable retry payload", async () => {
  const view = await render();
  const input = view.element.querySelector("[data-testid=community-reset-confirmation]");
  const submit = view.element.querySelector("[data-testid=community-reset-submit]");
  await act(async () => {
    Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value").set.call(
      input, resetConfirmation(run.run_id),
    );
    input.dispatchEvent(new Event("input", { bubbles: true }));
  });
  expect(submit.disabled).toBe(false);
  await act(async () => submit.click());
  expect(api.post).toHaveBeenCalledWith(
    "/simulator/community/controls/reset",
    resetPayload(run, resetConfirmation(run.run_id)),
  );
  expect(view.refresh).toHaveBeenCalledTimes(1);
  await act(async () => view.root.unmount());
});


test("passed gate still blocks submit until exact confirmation", async () => {
  const view = await render();
  const input = view.element.querySelector("[data-testid=community-reset-confirmation]");
  await act(async () => {
    Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value").set.call(
      input, "RESET another-run",
    );
    input.dispatchEvent(new Event("input", { bubbles: true }));
  });
  expect(view.element.querySelector("[data-testid=community-reset-submit]").disabled).toBe(true);
  expect(api.post).not.toHaveBeenCalled();
  await act(async () => view.root.unmount());
});
