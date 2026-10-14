import React, { act } from "react";
import { createRoot } from "react-dom/client";

jest.mock("@/lib/utils", () => ({ cn: (...values) => values.filter(Boolean).join(" ") }), { virtual: true });

import SimCommunityQueue from "../SimCommunityQueue";

globalThis.IS_REACT_ACT_ENVIRONMENT = true;

const queue = {
  status: "loaded", run_id: "run-7", overdue_after_minutes: 60, executor_behind_clock_minutes: 0,
  totals: { queued: 2, overdue: 1, in_progress: 1, longest_wait_minutes: 95 },
  departments: {
    kitchen: { label: "Kitchen", status: "on_duty", queued: 2, overdue: 1, longest_wait_minutes: 95, in_progress: 1, on_site: 1, busy: 1, free: 0, on_call: 0 },
    maintenance: { label: "Maintenance", status: "on_call", queued: 0, overdue: 0, longest_wait_minutes: null, in_progress: 0, on_site: 0, busy: 0, free: 0, on_call: 1 },
  },
  queued_shown: 2,
  queued: [
    { task_id: "task-old", department: "kitchen", priority: "normal", summary: "Offer scheduled lunch service.", waiting_minutes: 95, overdue: true },
    { task_id: "task-new", department: "kitchen", priority: "normal", summary: "Offer scheduled lunch service.", waiting_minutes: 7, overdue: false },
  ],
  workers: [{ actor_id: "sim:staff:kitchen:01", name: "Dining 01", department: "kitchen", job_role: "dining_team_member", availability: "busy", task_id: "task-busy" }],
  anomalies: [],
};

function render(props) {
  const container = document.createElement("div");
  const root = createRoot(container);
  act(() => root.render(<SimCommunityQueue {...props} />));
  return { container, root };
}

test("shows waits, overdue tickets, department capacity and busy workers with drill-in", () => {
  const opened = [];
  const { container, root } = render({ queue, runId: "run-7", onOpenRequest: (id) => opened.push(id) });
  expect(container.querySelector('[data-testid="queue-totals"]').textContent).toContain("1 h 35 min");
  expect(container.querySelector('[data-testid="queued-task-old"]').textContent).toContain("overdue");
  expect(container.querySelector('[data-testid="queued-task-new"]').textContent).toContain("Waiting 7 min");
  expect(container.querySelector('[data-status="on_call"]').textContent).toContain("On call");
  const worker = container.querySelector('[data-testid="worker-sim:staff:kitchen:01"]');
  expect(worker.textContent).toContain("Busy");
  act(() => worker.querySelector("button").click());
  act(() => container.querySelector('[data-testid="queued-task-old"] button').click());
  expect(opened).toEqual(["task-busy", "task-old"]);
  expect(container.querySelector('[data-testid="queue-executor-lag"]')).toBeNull();
  act(() => root.unmount());
});

test("an unknown or other-run queue is never shown as empty", () => {
  for (const props of [{ queue: { status: "error", run_id: "run-7" }, runId: "run-7" }, { queue, runId: "run-8" }]) {
    const { container, root } = render(props);
    expect(container.querySelector('[data-testid="queue-unknown"]').textContent).toContain("not evidence that nothing is waiting");
    expect(container.querySelector('[data-testid="queue-tickets"]')).toBeNull();
    act(() => root.unmount());
  }
});

test("a broken capacity rule is shown loudly", () => {
  const { container, root } = render({
    queue: { ...queue, anomalies: [{ kind: "worker_holds_multiple_active_tickets", actor_id: "sim:staff:x", task_ids: ["a", "b"] }] },
    runId: "run-7",
  });
  expect(container.querySelector('[data-testid="queue-anomalies"]').textContent).toContain("worker holds multiple active tickets");
  act(() => root.unmount());
});

test("executor lag behind the clock is stated, not hidden in waits", () => {
  const { container, root } = render({ queue: { ...queue, executor_behind_clock_minutes: 125 }, runId: "run-7" });
  expect(container.querySelector('[data-testid="queue-executor-lag"]').textContent).toContain("2 h 5 min behind");
  act(() => root.unmount());
});
