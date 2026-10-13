import React, { act } from "react";
import { createRoot } from "react-dom/client";

jest.mock("@/lib/utils", () => ({ cn: (...values) => values.filter(Boolean).join(" ") }), { virtual: true });
jest.mock("../lib/api", () => ({ api: { get: jest.fn(), post: jest.fn() } }));
jest.mock("sonner", () => ({ toast: { success: jest.fn(), error: jest.fn() } }));
jest.mock("../lib/communityRuntimeLoad", () => {
  const actual = jest.requireActual("../lib/communityRuntimeLoad");
  return { ...actual, fetchCommunityRuntimeSnapshot: jest.fn() };
});
jest.mock("../lib/communityObservedLoad", () => ({
  fetchCommunityObservedSnapshot: jest.fn(async () => ({ loadState: "error", snapshot: null })),
}));
jest.mock("../components/simulator/SimControls", () => () => null);
jest.mock("../components/simulator/SimActors", () => () => null);
jest.mock("../components/simulator/SimActivity", () => () => null);
jest.mock("../components/simulator/SimEventStream", () => () => null);
jest.mock("../components/simulator/SimReceiptTrace", () => () => null);
jest.mock("../components/simulator/SimCommunityOverview", () => () => null);
jest.mock("../components/simulator/SimCommunityObserved", () => () => null);
jest.mock("../components/simulator/SimCommunityResetControl", () => () => null);
jest.mock("./RequestDetailDialog", () => (props) => {
  const ReactModule = require("react");
  return props.open
    ? ReactModule.createElement("div", { "data-testid": "canonical-ticket-detail" }, props.taskId)
    : null;
});

import LiveOperations from "./LiveOperations";
import { api as mockApi } from "../lib/api";
import { fetchCommunityRuntimeSnapshot as mockFetchRuntime } from "../lib/communityRuntimeLoad";
import { fetchCommunityObservedSnapshot as mockFetchObserved } from "../lib/communityObservedLoad";

globalThis.IS_REACT_ACT_ENVIRONMENT = true;

const capability = {
  schema_version: 1,
  read_only: true,
  controls_enabled: true,
  mutations_allowed: true,
  transaction_probe: { status: "passed", supported: true, blocker: null },
  index_probe: { status: "passed", ready: true, required: [], blockers: [] },
  available_actions: ["pause", "resume", "stop"],
  step: { enabled: false, reason: "Durable cross-process exclusive-run capability is not verified." },
  blockers: [],
};

const receipt = (phase) => ({
  receipt_id: `receipt-${phase}`,
  task_id: "task-breakfast-1",
  action_type: phase === "pending" ? "resident_request_created" : `task_${phase}`,
  status: phase,
  actor: phase === "pending"
    ? { id: "sim:resident:001", type: "simulated-agent", name: "SIM Resident 001", channel: "scheduler" }
    : { id: "sim:staff:kitchen:01", type: "simulated-agent", name: "SIM Kitchen 01", channel: "scheduler" },
  authority: phase === "pending" ? "simulation_resident_routine" : "acts_for:kitchen",
  provenance_status: "complete",
  before_status: phase === "pending" ? null : phase === "in_progress" ? "pending" : "in_progress",
  after_status: phase,
  created_at: "2026-10-13T17:00:00+00:00",
});

function snapshot(phase, state = "RUNNING") {
  const cursor = phase === "pending" ? 1 : phase === "in_progress" ? 2 : 3;
  const transitions = phase === "pending"
    ? [receipt("pending")]
    : phase === "in_progress"
      ? [receipt("in_progress"), receipt("pending")]
      : [receipt("completed"), receipt("in_progress"), receipt("pending")];
  return {
    schema_version: 1,
    generated_at: "2026-10-13T17:00:00+00:00",
    status: "loaded",
    read_only: true,
    simulation_scope: "sim:community:living-80-v1:run-browser",
    community_id: "sim:community:living-80-v1",
    truth_statement: "Observed execution state from canonical records.",
    run: {
      status: "loaded", run_id: "run-browser", state,
      simulated_time: { absolute_minute: 480 + cursor, day_index: 0, minute: 480 + cursor, hh_mm: `08:0${cursor}` },
      cursor, event_count: 52_110,
      progress: { completed_events: cursor, total_events: 52_110, percent: 0.01 },
      next_event: { event_id: `event-${cursor + 1}`, action_type: "routine_ticket_phase", actor_name: "SIM Resident 001", department: "kitchen", blocked: false },
      last_evidence: { receipt_id: `receipt-${phase}`, status: "succeeded", action_type: transitions[0].action_type, actor_name: transitions[0].actor.name, actor_department: "kitchen" },
      resident_readiness: { status: "ready", residents_provisioned: true, expected_resident_count: 10, receipt_id: "ready-1", reason: null },
    },
    tickets: {
      status: "loaded",
      counts: {
        open: phase === "pending" ? 1 : 0,
        in_progress: phase === "in_progress" ? 1 : 0,
        completed: phase === "completed" ? 1 : 0,
        skipped: 0, other: 0, total: 1,
      },
    },
    staffing: { status: "loaded", coverage: { kitchen: { label: "Kitchen", on_shift: 1 } }, gaps: [], workers: [] },
    activity: {
      schema_version: 1, status: "loaded", read_only: true,
      run_id: "run-browser", simulation_scope: "living_community", community_id: "sim:community:living-80-v1",
      tasks: { status: "loaded", items: [{
        task_id: "task-breakfast-1", simulated: true,
        resident: { id: "sim:resident:001", name: "SIM Resident 001" },
        department: "kitchen", summary: "Prepare breakfast preference.", priority: "normal", status: phase,
        assigned_worker: phase === "pending" ? null : { id: "sim:staff:kitchen:01", name: "SIM Kitchen 01" },
        created_at: "2026-10-13T16:59:00+00:00", updated_at: "2026-10-13T17:00:00+00:00",
      }] },
      transitions: { status: "loaded", items: transitions },
    },
    sources: {
      runs: { status: "loaded" }, readiness: { status: "loaded" },
      tasks: { status: "loaded" }, receipts: { status: "loaded" },
    },
    errors: [],
  };
}

const ready = (value) => ({ loadState: "ready", snapshot: value });

async function flush() {
  await act(async () => { await Promise.resolve(); await Promise.resolve(); });
}

async function advance(milliseconds) {
  await act(async () => {
    jest.advanceTimersByTime(milliseconds);
    await Promise.resolve();
    await Promise.resolve();
  });
}

describe("Living Community browser acceptance", () => {
  let element;
  let root;

  beforeEach(() => {
    jest.useFakeTimers();
    jest.clearAllMocks();
    mockFetchObserved.mockResolvedValue({ loadState: "error", snapshot: null });
    mockApi.get.mockImplementation(async (path) => {
      if (path === "/simulator/community/controls/capability") return { data: capability };
      if (path === "/simulator/scenarios") return { data: [] };
      if (path === "/simulator/community/overview") return { data: {} };
      if (path === "/simulator/state") return { data: { state: "STOPPED", cast: null, run_id: null } };
      if (path === "/receipts") return { data: [] };
      throw new Error(`Unexpected GET ${path}`);
    });
    mockApi.post.mockResolvedValue({ data: { ok: true } });
    element = document.createElement("div");
    document.body.appendChild(element);
    root = createRoot(element);
  });

  afterEach(async () => {
    await act(async () => root.unmount());
    element.remove();
    jest.clearAllTimers();
    jest.useRealTimers();
  });

  test("owner watches one canonical ticket open, pause, resume, and complete with provenance", async () => {
    mockFetchRuntime
      .mockResolvedValueOnce(ready(snapshot("pending")))
      .mockResolvedValueOnce(ready(snapshot("pending")))
      .mockResolvedValueOnce(ready(snapshot("in_progress")))
      .mockResolvedValueOnce(ready(snapshot("in_progress", "PAUSED")))
      .mockResolvedValueOnce(ready(snapshot("in_progress", "PAUSED")))
      .mockResolvedValueOnce(ready(snapshot("in_progress", "PAUSED")))
      .mockResolvedValueOnce(ready(snapshot("in_progress")))
      .mockResolvedValueOnce(ready(snapshot("in_progress")))
      .mockResolvedValueOnce(ready(snapshot("completed")));

    await act(async () => root.render(<LiveOperations />));
    await flush();

    expect(element.querySelector("[data-testid=runtime-state]").textContent).toBe("RUNNING");
    expect(element.querySelector("[data-testid=runtime-ticket-counts]").textContent).toMatch(/Opened1.*In progress0.*Completed0/);
    expect(element.querySelector("[data-testid=community-live-tasks]").textContent).toMatch(/Prepare breakfast preference.*pending/i);
    expect(element.querySelector("[data-testid=community-live-transitions]").textContent)
      .toMatch(/SIM Resident 001.*simulated-agent.*scheduler.*simulation resident routine.*receipt-pending.*provenance complete/i);
    await act(async () => element.querySelector("[data-testid=community-task-task-breakfast-1] button").click());
    expect(element.querySelector("[data-testid=canonical-ticket-detail]").textContent).toBe("task-breakfast-1");

    await advance(2000);
    expect(element.querySelector("[data-testid=runtime-ticket-counts]").textContent).toMatch(/Opened0.*In progress1.*Completed0/);
    expect(element.querySelector("[data-testid=community-live-tasks]").textContent).toMatch(/in progress.*Assigned to SIM Kitchen 01/i);

    await act(async () => element.querySelector("[data-testid=community-control-pause]").click());
    await flush();
    expect(mockApi.post).toHaveBeenLastCalledWith("/simulator/community/controls/pause", expect.objectContaining({ run_id: "run-browser", expected_cursor: 2 }));
    expect(element.querySelector("[data-testid=runtime-state]").textContent).toBe("PAUSED");
    expect(element.querySelector("[data-testid=runtime-motion-status]").textContent).toMatch(/clock and autonomous work stay fixed.*real human actions can still appear/i);

    await advance(10000);
    expect(element.textContent).toMatch(/Cursor 2 of 52110/);
    expect(element.querySelector("[data-testid=community-live-tasks]").textContent).toMatch(/in progress/i);

    await act(async () => element.querySelector("[data-testid=community-control-resume]").click());
    await flush();
    expect(mockApi.post).toHaveBeenLastCalledWith("/simulator/community/controls/resume", expect.objectContaining({ run_id: "run-browser", expected_cursor: 2 }));
    expect(element.querySelector("[data-testid=runtime-state]").textContent).toBe("RUNNING");

    await advance(2000);
    expect(element.querySelector("[data-testid=runtime-ticket-counts]").textContent).toMatch(/Opened0.*In progress0.*Completed1/);
    expect(element.querySelector("[data-testid=community-live-tasks]").textContent).toMatch(/Prepare breakfast preference.*completed/i);
    expect(element.querySelector("[data-testid=community-live-transitions]").textContent)
      .toMatch(/task completed.*in progress.*completed.*SIM Kitchen 01.*acts for:kitchen.*receipt-completed.*provenance complete/i);
  });

  test("page leaves every control disabled when the safety gate is not proven", async () => {
    mockFetchRuntime.mockResolvedValue(ready(snapshot("in_progress", "PAUSED")));
    mockApi.get.mockImplementation(async (path) => {
      if (path === "/simulator/community/controls/capability") return { data: {
        ...capability, controls_enabled: false, mutations_allowed: false, available_actions: [],
        blockers: [{ code: "controls_not_enabled", message: "Living Community mutations are explicitly disabled." }],
      } };
      if (path === "/simulator/scenarios") return { data: [] };
      if (path === "/simulator/community/overview") return { data: {} };
      if (path === "/simulator/state") return { data: { state: "STOPPED", cast: null, run_id: null } };
      if (path === "/receipts") return { data: [] };
      throw new Error(`Unexpected GET ${path}`);
    });

    await act(async () => root.render(<LiveOperations />));
    await flush();

    expect(element.querySelector("[data-testid=community-controls-blockers]").textContent)
      .toMatch(/mutations are explicitly disabled/i);
    expect(element.querySelector("[data-testid=community-control-resume]").disabled).toBe(true);
    expect(element.querySelector("[data-testid=community-control-stop]").disabled).toBe(true);
    expect(element.querySelector("[data-testid=community-control-step]").disabled).toBe(true);
    expect(mockApi.post).not.toHaveBeenCalled();
  });
});
