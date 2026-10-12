// careops-transport-new-order-001: the admin Transportation screen had no way to
// start a ride (only Book on existing rows). It now opens the same canonical New
// ride form the calendar and front desk use, and refreshes the report after a save.
import React, { act } from "react";
import { createRoot } from "react-dom/client";

const report = {
  summary: { total_requests_received: 0, total_booked: 0, total_completed: 0, total_cancelled: 0, total_unresolved: 0, unresolved_scope: "" },
  inbound: [], outbound: [],
  current_state: { upcoming_rides: [], waiting_unbooked: [], follow_ups_required: [] },
};
const mockGet = jest.fn(() => Promise.resolve({ data: report }));
jest.mock("../../lib/api", () => ({ api: { get: (...a) => mockGet(...a), post: jest.fn() } }));
jest.mock("@/lib/utils", () => ({ cn: (...a) => a.filter(Boolean).join(" ") }), { virtual: true });
jest.mock("sonner", () => ({ toast: { error: jest.fn(), success: jest.fn() } }));
jest.mock("../../components/TransportAssignAction", () => () => null);
jest.mock("../../components/TransportUnresolvedList", () => () => null);
jest.mock("../RequestDetailDialog", () => () => null);
let formProps = null;
jest.mock("../../components/TransportRideForm", () => (p) => { formProps = p; return p.open ? <div data-testid="ride-form-open" /> : null; });

import TransportationTab from "../TransportationTab";

globalThis.IS_REACT_ACT_ENVIRONMENT = true;

test("New ride opens the canonical ride form and a save refreshes the report", async () => {
  mockGet.mockImplementation(() => Promise.resolve({ data: report }));   // CRA resets mock implementations per test
  const el = document.createElement("div");
  const root = createRoot(el);
  await act(async () => { root.render(<TransportationTab />); });
  const btn = el.querySelector("[data-testid=transport-new-ride]");
  expect(btn).not.toBeNull();
  expect(btn.textContent).toContain("New ride");
  expect(el.querySelector("[data-testid=ride-form-open]")).toBeNull();
  await act(async () => { btn.click(); });
  expect(el.querySelector("[data-testid=ride-form-open]")).not.toBeNull();
  expect(formProps.ride).toBeUndefined();          // a new ride, not a change
  const before = mockGet.mock.calls.length;
  await act(async () => { formProps.onSaved(); });
  expect(mockGet.mock.calls.length).toBe(before + 1);
  expect(mockGet.mock.calls[before][0]).toBe("/transportation/report");
  await act(async () => { root.unmount(); });
});
