/** RoutingExceptionsBoard: class chips carry the server counts, rows show classes/owner/latest/delivery, Re-send posts the receipted recovery and Open opens the request. */
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import { latestActionText, ageText } from "../routingExceptions";

const mockApi = { get: jest.fn(), post: jest.fn(), patch: jest.fn() };
jest.mock("../api", () => ({ api: mockApi, API: "http://api.test/api" }));
jest.mock("@/lib/utils", () => ({ cn: (...a) => a.filter(Boolean).join(" ") }), { virtual: true });
jest.mock("sonner", () => ({ toast: { error: jest.fn(), success: jest.fn() } }));
jest.mock("../../pages/RequestDetailDialog", () => (p) => { const R = require("react"); return p.open ? R.createElement("div", { "data-testid": "detail-open" }, p.taskId) : null; });
jest.mock("../../components/ui/card", () => { const R = require("react"); return { Card: (p) => R.createElement("div", { "data-testid": p["data-testid"] }, p.children) }; });
jest.mock("../../components/ui/badge", () => { const R = require("react"); return { Badge: (p) => R.createElement("span", { "data-testid": p["data-testid"] }, p.children) }; });
jest.mock("../../components/ui/button", () => { const R = require("react"); return { Button: (p) => R.createElement("button", { onClick: p.onClick, "data-testid": p["data-testid"] }, p.children) }; });

const Board = require("../../pages/RoutingExceptionsBoard").default;
globalThis.IS_REACT_ACT_ENVIRONMENT = true;
const flush = () => act(async () => { await Promise.resolve(); await Promise.resolve(); });
const data = { total: 2, counts: { undelivered: 1, unassigned: 2, overdue: 0, failed_handoff: 0 }, items: [
  { task_id: "t1", what: "Need help to the bathroom", department: "nursing", classes: ["undelivered", "unassigned"], age_seconds: 600, owner: null, times_asked: 1,
    latest_action: { field: "created", text: "aria_voice" }, delivery: { state: "not_sent", reached: false, label: "Department NOT notified: recorded only" }, notification_attempts: 1, receipts_count: 1, escalation: { refused_steps: 0 }, currency: { bucket: "current" } },
  { task_id: "t2", what: "Extra coffee", department: "kitchen", classes: ["unassigned"], age_seconds: 7200, owner: null, times_asked: 2,
    latest_action: { field: "re_request" }, delivery: { state: "delivered", reached: true, label: "Department notified (delivery confirmed)" }, notification_attempts: 1, receipts_count: 2, escalation: { refused_steps: 0 }, currency: { bucket: "current" } },
] };
let root, el;
beforeEach(() => { el = document.createElement("div"); document.body.appendChild(el); root = createRoot(el); mockApi.get.mockReset(); mockApi.post.mockReset(); });
afterEach(async () => { await act(async () => root.unmount()); el.remove(); });
const q = (id) => el.querySelector(`[data-testid="${id}"]`);

test("wording helpers", () => {
  expect(latestActionText({ field: "assigned_to", to: "u1", by_name: "Iris" })).toBe("Assigned by Iris");
  expect(latestActionText({ field: "created", text: "aria_voice" })).toBe("Created (aria_voice)");
  expect(ageText(90)).toBe("1m"); expect(ageText(7200)).toBe("2h"); expect(ageText(3 * 86400)).toBe("3d");
});

test("chips show server counts; rows show classes, latest action and delivery; Re-send only where not reached", async () => {
  mockApi.get.mockResolvedValue({ data }); mockApi.post.mockResolvedValue({ data: { delivery: { reached: false, label: "recorded only" } } });
  await act(async () => root.render(<Board />)); await flush();
  expect(q("rx-kind-undelivered").textContent).toBe("Not delivered (1)");
  expect(q("rx-kind-all").textContent).toBe("All (2)");
  expect(q("rx-class-t1-undelivered").textContent).toBe("Not delivered");
  expect(q("rx-latest-t2").textContent).toBe("Latest: Asked again");
  expect(q("rx-delivery-t1").textContent).toMatch(/^Department NOT notified/);
  expect(q("rx-renotify-t2")).toBeNull();
  await act(async () => { q("rx-renotify-t1").click(); }); await flush();
  expect(mockApi.post).toHaveBeenCalledWith("/ops/routing-exceptions/t1/renotify");
  await act(async () => { q("rx-open-t2").click(); });
  expect(q("detail-open").textContent).toBe("t2");
});

test("a class chip refilters through the server and a failed read shows an error, not an empty list", async () => {
  mockApi.get.mockResolvedValue({ data });
  await act(async () => root.render(<Board />)); await flush();
  await act(async () => { q("rx-kind-unassigned").click(); }); await flush();
  expect(mockApi.get).toHaveBeenLastCalledWith("/ops/routing-exceptions", { params: { kind: "unassigned", include_review: false } });
  mockApi.get.mockRejectedValue(new Error("x"));
  await act(async () => { q("rx-refresh").click(); }); await flush();
  expect(q("rx-error")).not.toBeNull();
});

test("escalation steps read plainly in the latest action", () => {
  const { latestActionText } = require("../routingExceptions");
  expect(latestActionText({ field: "unclaimed_escalated", by_name: "Escalation tick" })).toMatch(/Flagged to a supervisor \(unclaimed\)/);
  expect(latestActionText({ field: "escalated", by_name: "Nurse" })).toMatch(/Couldn't complete/);
});
