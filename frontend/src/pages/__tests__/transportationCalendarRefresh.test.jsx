// RQ-020: a parent's refresh (refreshKey) reloads the calendar data but must
// not reset the day the front desk is looking at back to today.
import React, { act } from "react";
import { createRoot } from "react-dom/client";

const mockGet = jest.fn(() => Promise.resolve({ data: { days: [{ date: "2026-10-12", runs: [], pending: [] }] } }));
jest.mock("../../lib/api", () => ({ api: { get: (...a) => mockGet(...a) } }));
jest.mock("../../lib/auth", () => ({ useAuth: () => ({ user: { role: "front_desk" } }) }));
// jest has no "@/" alias here; the ui primitives only need cn()
jest.mock("@/lib/utils", () => ({ cn: (...a) => a.filter(Boolean).join(" ") }), { virtual: true });
jest.mock("sonner", () => ({ toast: { error: jest.fn() } }));
jest.mock("../../components/TransportAssignAction", () => () => null);
jest.mock("../../components/TransportRunCard", () => () => null);
jest.mock("../../components/TransportRideForm", () => () => null);
jest.mock("../../components/TransportCancelDialog", () => () => null);
jest.mock("../RequestHistoryDialog", () => () => null);

import TransportationCalendar from "../TransportationCalendar";

globalThis.IS_REACT_ACT_ENVIRONMENT = true;

test("refreshKey refetches the same day instead of resetting to today", async () => {
  const el = document.createElement("div");
  const root = createRoot(el);
  await act(async () => { root.render(<TransportationCalendar refreshKey={0} />); });
  const next = el.querySelector("[data-testid=calendar-next]");
  await act(async () => { next.click(); });
  const dateOf = () => mockGet.mock.calls[mockGet.mock.calls.length - 1][1].params.date;
  const moved = dateOf();
  const callsBefore = mockGet.mock.calls.length;
  await act(async () => { root.render(<TransportationCalendar refreshKey={1} />); });
  expect(mockGet.mock.calls.length).toBe(callsBefore + 1);
  expect(dateOf()).toBe(moved);
  expect(el.querySelector("[data-testid=calendar-date-picker]").value).toBe(moved);
  await act(async () => { root.unmount(); });
});
