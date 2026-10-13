import React, { act } from "react";
import { createRoot } from "react-dom/client";

jest.mock("@/lib/utils", () => ({ cn: (...values) => values.filter(Boolean).join(" ") }), { virtual: true });

import SimCommunityRuntime from "../SimCommunityRuntime";
import { communityRuntimeIntro, fetchCommunityRuntimeSnapshot } from "../../../lib/communityRuntimeLoad";

globalThis.IS_REACT_ACT_ENVIRONMENT = true;

const loaded = {
  schema_version: 1,
  generated_at: "2026-10-13T17:00:00+00:00",
  status: "loaded",
  read_only: true,
  simulation_scope: "sim:community:living-80-v1:run-7",
  community_id: "sim:community:living-80-v1",
  truth_statement: "Observed execution state; the planning preview is not execution evidence.",
  run: {
    status: "loaded", run_id: "run-7", state: "RUNNING",
    simulated_time: { absolute_minute: 480, day_index: 0, minute: 480, hh_mm: "08:00" },
    cursor: 12, event_count: 120, progress: { completed_events: 12, total_events: 120, percent: 10 },
    next_event: {
      event_id: "event-13", action_type: "resident_routine_due", actor_name: "Avery Brooks",
      department: "nursing", blocked: false,
    },
    last_evidence: {
      receipt_id: "receipt-12", status: "succeeded", action_type: "resident_routine_created",
      actor_name: "Taylor Reed", actor_department: "nursing",
    },
    resident_readiness: {
      status: "ready", residents_provisioned: true, expected_resident_count: 10,
      receipt_id: "ready-1", reason: null,
    },
  },
  tickets: {
    status: "loaded",
    counts: { open: 4, in_progress: 2, completed: 6, skipped: 0, other: 0, total: 12 },
  },
  staffing: {
    status: "loaded", basis: "deterministic_schedule_at_persisted_simulated_time", day_index: 0, minute: 480,
    workers: [],
    coverage: {
      nursing: { label: "Nursing / Care", on_shift: 4, actor_ids: [], job_roles: [] },
      maintenance: { label: "Maintenance", on_shift: 0, actor_ids: [], job_roles: [] },
    },
    gaps: ["maintenance"],
  },
  sources: {
    runs: { status: "loaded", error: null },
    readiness: { status: "loaded", error: null },
    tasks: { status: "loaded", error: null },
    receipts: { status: "loaded", error: null },
  },
  activity: {
    schema_version: 1, status: "loaded", read_only: true,
    run_id: "run-7", simulation_scope: "living_community", community_id: "sim:community:living-80-v1",
    tasks: { status: "loaded", items: [{
      task_id: "task-7", simulated: true,
      resident: { id: "sim:resident:007", name: "SIM Resident 007" },
      department: "housekeeping", category: "housekeeping", summary: "Scheduled simulated room care.",
      priority: "normal", status: "in_progress",
      assigned_worker: { id: "sim:staff:housekeeping:01", name: "SIM Housekeeper 01" },
      created_at: "2026-10-13T16:59:00+00:00", updated_at: "2026-10-13T17:00:00+00:00",
    }] },
    transitions: { status: "loaded", items: [{
      receipt_id: "rcpt-task-7", task_id: "task-7", action_type: "task_started", status: "in_progress",
      actor: { id: "sim:staff:housekeeping:01", type: "simulated-agent", name: "SIM Housekeeper 01" },
      authority: "acts_for:housekeeping", provenance_status: "complete",
      before_status: "pending", after_status: "in_progress", created_at: "2026-10-13T17:00:00+00:00",
    }] },
  },
  errors: [],
};

const nullCounts = { open: null, in_progress: null, completed: null, skipped: null, other: null, total: null };

async function render(props) {
  const element = document.createElement("div");
  const root = createRoot(element);
  await act(async () => root.render(<SimCommunityRuntime onRetry={() => {}} {...props} />));
  return { element, root };
}

test("validates and loads the read-only runtime contract", async () => {
  const client = { get: jest.fn().mockResolvedValue({ data: loaded }) };
  await expect(fetchCommunityRuntimeSnapshot(client)).resolves.toEqual({ loadState: "ready", snapshot: loaded });
  expect(client.get).toHaveBeenCalledWith("/simulator/community/runtime");

  const invalid = { ...loaded, tickets: { status: "error", counts: { ...nullCounts, open: undefined } } };
  await expect(fetchCommunityRuntimeSnapshot({ get: jest.fn().mockResolvedValue({ data: invalid }) }))
    .resolves.toEqual({ loadState: "error", snapshot: null });
});

test("intro distinguishes an active community run from plan-only and unknown reads", () => {
  expect(communityRuntimeIntro(loaded)).toMatch(/canonical execution truth.*active living-community run/i);
  expect(communityRuntimeIntro({ run: { status: "not_started", state: null } })).toMatch(/planning preview.*no living-community run/i);
  expect(communityRuntimeIntro(null)).toMatch(/unavailable read never proves.*stopped/i);
});

test("shows a loaded active run, canonical ticket movement, coverage, next work, and receipt", async () => {
  const opened = jest.fn();
  const { element, root } = await render({ loadState: "ready", snapshot: loaded, onOpenRequest: opened });
  expect(element.querySelector("[data-testid=runtime-state]").textContent).toContain("RUNNING");
  expect(element.textContent).toMatch(/Day 1.*08:00/);
  expect(element.textContent).toMatch(/Cursor.*12 of 120/);
  expect(element.querySelector("[data-testid=runtime-ticket-counts]").textContent)
    .toMatch(/Opened4.*In progress2.*Completed6/);
  expect(element.querySelector("[data-testid=runtime-next-event]").textContent)
    .toMatch(/resident routine due.*Avery Brooks.*nursing.*event-13/i);
  expect(element.querySelector("[data-testid=runtime-last-receipt]").textContent)
    .toMatch(/resident routine created.*succeeded.*Taylor Reed.*receipt-12/i);
  expect(element.querySelector("[data-testid=runtime-coverage]").textContent)
    .toMatch(/Nursing \/ Care.*4 on shift.*Maintenance.*0 on shift/);
  expect(element.querySelector("[data-testid=runtime-coverage-gaps]").textContent).toMatch(/maintenance/i);
  expect(element.querySelector("[data-testid=community-live-tasks]").textContent)
    .toMatch(/Simulated.*housekeeping.*Scheduled simulated room care.*SIM Resident 007.*in progress/i);
  expect(element.querySelector("[data-testid=community-live-transitions]").textContent)
    .toMatch(/task started.*pending.*in progress.*SIM Housekeeper 01.*provenance complete/i);
  await act(async () => element.querySelector("[data-testid=community-task-task-7] button").click());
  expect(opened).toHaveBeenCalledWith("task-7");
  await act(async () => root.unmount());
});

test("no-run state says the plan is not running and never turns null counts into zero", async () => {
  const snapshot = {
    ...loaded,
    status: "unknown",
    run: {
      status: "not_started", run_id: null, state: null,
      simulated_time: { absolute_minute: null, day_index: null, minute: null, hh_mm: null },
      cursor: null, event_count: null,
      progress: { completed_events: null, total_events: null, percent: null },
      next_event: null, last_evidence: null,
      resident_readiness: {
        status: "not_started", residents_provisioned: null, expected_resident_count: 10,
        receipt_id: null, reason: null,
      },
    },
    tickets: { status: "not_started", counts: nullCounts },
    staffing: { status: "not_started", coverage: null, gaps: null, workers: [] },
  };
  const { element, root } = await render({ loadState: "ready", snapshot });
  expect(element.querySelector("[data-testid=runtime-state]").textContent).toContain("NOT STARTED");
  expect(element.textContent).toMatch(/90-day plan is not running/i);
  expect(element.querySelector("[data-testid=runtime-ticket-counts]").textContent)
    .toMatch(/OpenedUnknown.*In progressUnknown.*CompletedUnknown/);
  expect(element.querySelector("[data-testid=runtime-ticket-counts]").textContent).not.toContain("0");
  expect(element.textContent).toMatch(/Coverage is unknown/);
  await act(async () => root.unmount());
});

test("partial source errors and failed refresh stay visibly unknown or stale", async () => {
  const snapshot = {
    ...loaded,
    status: "error",
    tickets: { status: "error", counts: nullCounts },
    staffing: { status: "unknown", coverage: null, gaps: null, workers: [] },
    sources: {
      runs: { status: "loaded", error: null },
      readiness: { status: "loaded", error: null },
      tasks: { status: "error", error: "read_failed" },
      receipts: { status: "unknown", error: "timeout" },
    },
  };
  let view = await render({ loadState: "ready", snapshot });
  expect(view.element.querySelector("[data-testid=community-runtime-partial]").textContent).toMatch(/truth is error/i);
  expect(view.element.querySelector("[data-testid=runtime-ticket-counts]").textContent).not.toContain("0");
  expect(view.element.textContent).toMatch(/Ticket read: error.*Staffing read: unknown.*tasks: error.*receipts: unknown/i);
  await act(async () => view.root.unmount());

  view = await render({ loadState: "error", snapshot, refreshFailed: true });
  expect(view.element.querySelector("[data-testid=community-runtime-stale]").textContent)
    .toMatch(/last received read.*not replaced with zero/i);
  await act(async () => view.root.unmount());
});

test("initial load failure does not infer engine or ticket state", async () => {
  const { element, root } = await render({ loadState: "error", snapshot: null });
  expect(element.textContent).toMatch(/runtime unknown/i);
  expect(element.textContent).toMatch(/not evidence that the engine is running, stopped/i);
  expect(element.textContent).toMatch(/zero tickets/i);
  await act(async () => root.unmount());
});

test("activity mismatch or read failure stays unknown rather than falsely empty", async () => {
  const mismatch = { ...loaded, activity: { ...loaded.activity, run_id: "another-run" } };
  let view = await render({ loadState: "ready", snapshot: mismatch });
  expect(view.element.textContent).toMatch(/Live canonical activity.*unknown.*tickets are unknown/i);
  expect(view.element.textContent).not.toMatch(/exact run has no canonical tickets/i);
  await act(async () => view.root.unmount());

  const failed = {
    ...loaded,
    status: "error",
    activity: {
      ...loaded.activity,
      status: "error",
      tasks: { status: "error", items: null },
      transitions: { status: "error", items: null },
    },
  };
  view = await render({ loadState: "ready", snapshot: failed });
  expect(view.element.textContent).toMatch(/tickets are unknown.*transitions are unknown/i);
  await act(async () => view.root.unmount());
});
