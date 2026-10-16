import React, { act } from "react";
import { createRoot } from "react-dom/client";

jest.mock("@/lib/utils", () => ({ cn: (...values) => values.filter(Boolean).join(" ") }), { virtual: true });
jest.mock("sonner", () => ({ toast: { success: jest.fn(), error: jest.fn() } }));
jest.mock("../../../lib/api", () => ({ api: { get: jest.fn(), post: jest.fn() } }));
jest.mock("../../../pages/RequestDetailDialog", () => ({ taskId, open }) => (
  open ? <div data-testid="task-detail">{taskId}</div> : null));

import OverviewDepartments from "../OverviewDepartments";
import { api } from "../../../lib/api";

globalThis.IS_REACT_ACT_ENVIRONMENT = true;

// #153 slice 2: Nursing Done Today, Nursing Open and Kitchen Done Today open
// exactly the records they count.
const SCOPE = {
  world: "live", date: "2026-10-15", timezone: "America/Chicago", exact_columns: ["open", "completed_today"],
  unverified_columns: ["overdue", "unassigned", "in_progress"],
  unverified_reason: "UNVERIFIED: includes 12 simulated task records alongside live ones.",
  explanation: "Open and done today count live records only.",
};
const DEPTS = [
  { slug: "nursing", label: "Nursing / Care", active: true, open: 2, overdue: 0, unassigned: 1, in_progress: 1, completed_today: 3 },
  { slug: "kitchen", label: "Kitchen", active: true, open: 0, overdue: 0, unassigned: 0, in_progress: 0, completed_today: 7 },
];
const row = (id, extra = {}) => ({ task_id: id, summary: `Task ${id}`, status: "completed", department: "Nursing / Care",
  origin: "resident_request", origin_label: "Resident request", world: "live", actor_kind: "real", worker: "Real Nurse",
  created_at: "2026-10-15T14:00:00Z", completed_at: "2026-10-15T15:00:00Z", ...extra });
const RECORDS = {
  "done:nursing": [row("t1"), row("t2"), row("t3")],
  "open:nursing": [row("w1", { status: "pending", actor_kind: "none", worker: null }), row("w2", { status: "in_progress" })],
  "done:kitchen": [1, 2, 3, 4, 5, 6].map((i) => row(`k${i}`, { department: "Kitchen" })),   // one fewer than the tile's 7
};

beforeEach(() => {
  api.get.mockReset();
  api.get.mockImplementation((url, { params }) => {
    if (url !== "/ops/metrics/records") return Promise.reject(new Error(`unexpected ${url}`));
    const rows = RECORDS[`${params.metric}:${params.department}`] || [];
    const all = params.origin ? [] : rows;
    return Promise.resolve({ data: { metric: params.metric, world: "live", total: all.length, matched: all.length,
      page: params.page || 1, page_size: params.page_size || 50, rows: params.page_size === 1 ? all.slice(0, 1) : all,
      period: { kind: "wall_date", date: params.date, timezone: "America/Chicago", label: `${params.date} (America/Chicago)` },
      timezone: "America/Chicago", status_filter: params.metric === "open" ? ["pending", "in_progress"] : ["completed"],
      facility: { name: "Conway", basis: "The only facility in this database; tasks carry no facility_id." },
      explanation: "Tasks in Nursing / Care…", run: null } });
  });
});

async function mount() {
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  await act(async () => root.render(<OverviewDepartments departments={DEPTS} scope={SCOPE} onNavigate={() => {}} />));
  return { host, root };
}

async function openMetric(testid) {
  const button = document.querySelector(`[data-testid="${testid}"]`);
  expect(button.tagName).toBe("BUTTON");             // native button: Tab focus + Enter/Space activation
  await act(async () => { button.focus(); button.click(); });
  await act(async () => {});
  return document.querySelector('[data-testid="ws-records"]');
}

const recordCalls = () => api.get.mock.calls.filter(([, { params }]) => params.page_size !== 1).map(([, c]) => c.params);

test.each([
  ["ops-metric-nursing-completed_today", "done", "nursing", 3],
  ["ops-metric-nursing-open", "open", "nursing", 2],
])("%s opens exactly the records it counts", async (testid, metric, department, shown) => {
  const { root } = await mount();
  expect(document.querySelector(`[data-testid="${testid}"]`).textContent).toContain(String(shown));
  const dialog = await openMetric(testid);
  expect(recordCalls()[0]).toMatchObject({ metric, department, world: "live", date: "2026-10-15" });
  const ids = dialog.querySelectorAll('[data-testid="ws-record-open"]');
  expect(ids).toHaveLength(shown);                                   // numerator == rows returned
  ids.forEach((b) => expect(b.tagName).toBe("BUTTON"));
  expect(dialog.querySelector('[data-testid="ws-unverified"]')).toBeNull();
  const disclosure = dialog.querySelector('[data-testid="ws-disclosure"]').textContent;
  ["Conway", "Live records only", "real wall date", "America/Chicago", metric === "open" ? "pending or in_progress" : "completed"]
    .forEach((fact) => expect(disclosure).toContain(fact));
  await act(async () => { ids[0].focus(); ids[0].click(); });         // task id → its detail and receipts
  expect(document.querySelector('[data-testid="task-detail"]').textContent).toBe(RECORDS[`${metric}:${department}`][0].task_id);
  act(() => root.unmount());
});

test("open rows say whether a real person, a simulated worker or nobody holds them", async () => {
  const { root } = await mount();
  const dialog = await openMetric("ops-metric-nursing-open");
  expect(dialog.textContent).toContain("not claimed");
  expect(dialog.textContent).toContain("real person");
  act(() => root.unmount());
});

test("Kitchen Done Today shows UNVERIFIED with the reason when the records no longer match the box", async () => {
  const { root } = await mount();
  const dialog = await openMetric("ops-metric-kitchen-completed_today");
  expect(dialog.querySelectorAll('[data-testid="ws-record-open"]')).toHaveLength(6);
  expect(dialog.querySelector('[data-testid="ws-unverified"]').textContent).toMatch(/UNVERIFIED: the box showed 7 but 6 records match now/);
  act(() => root.unmount());
});

test("columns counted from the loaded list are not drill-downs and carry the backend's reason", async () => {
  const { root } = await mount();
  const card = document.querySelector('[data-testid="ops-dept-nursing"]');
  expect(card.querySelectorAll("button")).toHaveLength(3);           // department link + open + done today
  expect(card.textContent).toContain("Unverified");
  expect(document.querySelector('[data-testid="ops-dept-unverified"]').textContent).toContain(SCOPE.unverified_reason);
  act(() => root.unmount());
});
