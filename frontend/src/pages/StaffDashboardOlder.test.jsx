import React, { act } from "react";
import { createRoot } from "react-dom/client";

jest.mock("react-router-dom", () => ({ Link: ({ children }) => children, useNavigate: () => jest.fn(),
  useSearchParams: () => [new URLSearchParams()] }), { virtual: true });
jest.mock("./AlertDetailDialog", () => () => null);
jest.mock("./PagerFeedCard", () => () => null);
jest.mock("./DeviceStatusCard", () => () => null);
jest.mock("./DepartmentQueue", () => () => null);
jest.mock("./TasksTab", () => ({ MyTasksCard: () => null }));
jest.mock("../lib/api", () => ({ api: { get: jest.fn(), post: jest.fn() } }));
jest.mock("../lib/auth", () => ({ useAuth: () => ({ user: { name: "Nurse", role: "staff", department: "nursing" }, logout: jest.fn() }) }));
jest.mock("@/lib/utils", () => ({ cn: (...args) => args.filter(Boolean).join(" ") }), { virtual: true });
jest.mock("sonner", () => ({ toast: { success: jest.fn(), error: jest.fn() } }));

import { api } from "../lib/api";
import StaffDashboard from "./StaffDashboard";

globalThis.IS_REACT_ACT_ENVIRONMENT = true;

const now = new Date().toISOString();
const cur = { alert_id: "a-new", severity: "assist", status: "active", room: "3W03", triggered_by: "kiosk_button", created_at: now, event_log: [] };
const old = { alert_id: "a-old", severity: "emergency", status: "active", room: "214", triggered_by: "rf_pendant", created_at: "2026-09-20T07:00:00Z", event_log: [] };

test("Live alerts lists current alerts; older ones are counted and shown only on request", async () => {
  api.get.mockImplementation((u, cfg) => {
    if (u === "/alerts/feed") return Promise.resolve({ data: cfg?.params?.scope === "older" ? [old] : [cur] });
    if (u === "/alerts/stats") return Promise.resolve({ data: { active: 1, acknowledged: 0, resolved_24h: 0, emergency_active: 0, older_open: 1 } });
    return Promise.resolve({ data: [] });
  });
  const el = document.createElement("div");
  const root = createRoot(el);
  await act(async () => { root.render(<StaffDashboard />); });
  const q = (id) => el.querySelector(`[data-testid="${id}"]`);
  expect(q("alert-card-a-new")).not.toBeNull();
  expect(q("alert-card-a-old")).toBeNull();
  expect(q("alerts-older-banner").textContent).toMatch(/1 older open alert is hidden/);
  expect(q("alerts-older-banner").textContent).toMatch(/Nothing was closed/);
  await act(async () => { q("alerts-older-toggle").click(); });
  expect(q("alert-card-a-old")).not.toBeNull();
  expect(q("alert-older-a-old").textContent).toBe("older");
  expect(q("alerts-older-banner").textContent).toMatch(/Showing 1 of 1 older open alert too/);
  expect(q("alert-older-a-new")).toBeNull();
  expect(el.querySelector("[data-testid=alerts-list]").firstElementChild.getAttribute("data-testid")).toBe("alert-card-a-new");
  await act(async () => { root.unmount(); });
});
