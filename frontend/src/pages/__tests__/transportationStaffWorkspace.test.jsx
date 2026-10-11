import React, { act } from "react";
import { createRoot } from "react-dom/client";

const mockGet = jest.fn(() => Promise.resolve({
  data: {
    linked_driver: { driver_id: "drv-1", name: "Pete Nash" },
    days: [{
      date: "2026-10-10",
      pending: [],
      runs: [{
        run_id: "run-1", date: "2026-10-10", depart_time: "10:00", status: "confirmed",
        riders: [{ task_id: "task-1", resident_name: "Demo Resident", status: "pending", purpose: "clinic" }],
      }],
    }],
  },
}));

jest.mock("../../lib/api", () => ({ api: { get: (...args) => mockGet(...args) } }));
jest.mock("../../lib/auth", () => ({
  useAuth: () => ({ user: { role: "staff", department: "transportation", name: "Pete Nash" } }),
}));
jest.mock("@/lib/utils", () => ({ cn: (...args) => args.filter(Boolean).join(" ") }), { virtual: true });
jest.mock("sonner", () => ({ toast: { error: jest.fn() } }));
jest.mock("../../components/TransportAssignAction", () => () => null);
jest.mock("../../components/TransportRideForm", () => () => null);
jest.mock("../../components/TransportCancelDialog", () => () => null);
jest.mock("../../components/TransportRunDetailsDialog", () => () => null);
jest.mock("../RequestHistoryDialog", () => () => null);

import TransportationCalendar from "../TransportationCalendar";

globalThis.IS_REACT_ACT_ENVIRONMENT = true;

test("transportation staff see trip creation in their workspace", async () => {
  const el = document.createElement("div");
  const root = createRoot(el);
  await act(async () => { root.render(<TransportationCalendar />); });

  expect(el.querySelector("[data-testid=calendar-new-ride]")).not.toBeNull();
  expect(el.querySelector("[data-testid=calendar-mine-toggle]").textContent).toContain("My rides");

  await act(async () => { root.unmount(); });
});
