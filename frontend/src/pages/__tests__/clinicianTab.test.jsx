// careops-clinician-workspace-001: purpose stated; a failed load is an error (not "no data");
// events open the alert close-out dialog; older open records flagged; summary from the briefing.
import React, { act } from "react";
import { createRoot } from "react-dom/client";

const mockGet = jest.fn();
jest.mock("../../lib/api", () => ({ api: { get: (...a) => mockGet(...a) } }));
jest.mock("@/lib/utils", () => ({ cn: (...a) => a.filter(Boolean).join(" ") }), { virtual: true });
jest.mock("../../components/ui/select", () => {
  const none = () => null;
  return { Select: none, SelectContent: none, SelectItem: none, SelectTrigger: none, SelectValue: none };
});
let dialogProps = null;
jest.mock("../AlertDetailDialog", () => (p) => { dialogProps = p; return null; });

import ClinicianTab from "../ClinicianTab";
globalThis.IS_REACT_ACT_ENVIRONMENT = true;
const residents = [{ resident_id: "r1", name: "Pat", room: "T1" }];
const win = (o) => ({ total_calls: 2, by_category: { fall: 1 }, by_severity: {}, avg_response_s: 30, avg_duration_s: 60, falls_during_call: 1, unresolved: 2, unresolved_older: 1, ...o });
const old = new Date(Date.now() - 10 * 86400000).toISOString();
const stats = { current_window: win(), previous_window: win({ total_calls: 0, unresolved: 0, unresolved_older: 0, by_category: {} }),
  recent_events: [{ alert_id: "a1", created_at: old, category: "fall", severity: "assist", status: "active" }] };
const flush = () => act(async () => { await Promise.resolve(); await Promise.resolve(); });

async function mount() {
  const el = document.createElement("div"); const root = createRoot(el);
  await act(async () => { root.render(<ClinicianTab residents={residents} />); });
  await flush();
  return { el, root };
}

test("loaded: purpose, older flag, summary, and an event opens the close-out", async () => {
  mockGet.mockImplementation((u) => Promise.resolve({ data: u.includes("/briefing") ? { narrative: "Pat has 2 open alerts." } : stats }));
  const { el, root } = await mount();
  expect(el.querySelector("[data-testid=clinician-purpose]").textContent).toMatch(/not a medical record/);
  expect(el.querySelector("[data-testid=kpi-unresolved-older]").textContent).toBe("1 older than 3 days, need review");
  expect(el.querySelector("[data-testid=event-older-a1]")).not.toBeNull();
  expect(el.querySelector("[data-testid=clinician-summary]").textContent).toBe("Pat has 2 open alerts.");
  await act(async () => { el.querySelector("[data-testid=event-a1]").click(); });
  expect(dialogProps.alertId).toBe("a1"); expect(dialogProps.open).toBe(true);
  await act(async () => { root.unmount(); });
});

test("a refused load shows the reason, not 'no data'", async () => {
  mockGet.mockImplementation(() => Promise.reject({ response: { status: 403 } }));
  const { el, root } = await mount();
  expect(el.querySelector("[data-testid=clinician-error]").textContent).toMatch(/administrators and nursing staff/);
  expect(el.textContent).not.toMatch(/No data/);
  await act(async () => { root.unmount(); });
});
