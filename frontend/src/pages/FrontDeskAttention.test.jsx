import React, { act } from "react";
import { createRoot } from "react-dom/client";

jest.mock("react-router-dom", () => ({ Link: ({ children, to, ...p }) => <a href={to} {...p}>{children}</a> }), { virtual: true });
jest.mock("../lib/auth", () => ({ useAuth: () => ({ user: { name: "Dana", role: "front_desk" }, logout: jest.fn() }) }));
jest.mock("../lib/api", () => ({ api: { get: jest.fn(), post: jest.fn() } }));
jest.mock("@/lib/utils", () => ({ cn: (...args) => args.filter(Boolean).join(" ") }), { virtual: true });
jest.mock("sonner", () => ({ toast: { success: jest.fn(), error: jest.fn() } }));
jest.mock("./TransportationCalendar", () => () => null);
jest.mock("./TransportLog", () => () => null);
jest.mock("./RequestsBoard", () => () => null);
jest.mock("./DepartmentQueue", () => () => null);
jest.mock("./RequestDetailDialog", () => () => null);
jest.mock("../components/FrontDeskRequestForm", () => () => null);
jest.mock("../components/FrontDeskResidentDirectory", () => () => null);
jest.mock("../components/TransportRideForm", () => () => null);

import { api } from "../lib/api";
import FrontDeskDashboard from "./FrontDeskDashboard";

globalThis.IS_REACT_ACT_ENVIRONMENT = true;

test("front desk has a Needs attention tab showing its scoped routing exceptions", async () => {
  api.get.mockImplementation((u) => Promise.resolve({ data: u === "/ops/delivery-exceptions"
    ? { total: 1, counts: { failed: 1, not_sent: 0 }, items: [{ notification_id: "n1", alert_id: "al1", channel: "email",
        recipient: "Family: Liam Example (son)", state: "failed", label: "Failed - the provider did not accept it",
        resident_name: "Betty Owusu", room: "3W03", alert_severity: "emergency", alert_status: "active",
        receipt_id: "rcpt_1", created_at: new Date().toISOString() }] }
    : u === "/ops/routing-exceptions"
    ? { total: 1, counts: { undelivered: 1 }, items: [{ task_id: "t1", classes: ["undelivered"], department: "administration",
        what: "Callback about the September bill", age_seconds: 600, delivery: { reached: false, label: "not sent" },
        notification_attempts: 1, receipts_count: 2, latest_action: null }] }
    : [] }));
  const el = document.createElement("div");
  const root = createRoot(el);
  await act(async () => { root.render(<FrontDeskDashboard />); });
  const q = (id) => el.querySelector(`[data-testid="${id}"]`);
  expect(q("fd-tab-attention")).not.toBeNull();
  await act(async () => { q("fd-tab-attention").click(); });
  expect(api.get).toHaveBeenCalledWith("/ops/routing-exceptions", expect.anything());
  expect(q("rx-row-t1").textContent).toMatch(/Callback about the September bill/);
  expect(q("rx-renotify-t1")).not.toBeNull();
  // alert deliveries that did not go out, without message text
  const d = q("dx-row-n1");
  expect(d.textContent).toMatch(/Family: Liam Example \(son\)/);
  expect(d.textContent).toMatch(/Failed - the provider did not accept it/);
  expect(d.textContent).toMatch(/Betty Owusu/);
  expect(q("dx-open-n1").getAttribute("href")).toBe("/staff?alert=al1");
  await act(async () => { root.unmount(); });
});
