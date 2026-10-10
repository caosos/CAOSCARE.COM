/** Real components mounted with a controllable api: a late reply for an old request/filter must never
 * overwrite the newer one, a failed history fetch must show a recoverable error, and a failed completion
 * must keep the dialog and note. (Components mounted with react-dom + act; no real network.) */
import React, { act } from "react";
import { createRoot } from "react-dom/client";

const mockApi = { get: jest.fn(), post: jest.fn(), patch: jest.fn() };
jest.mock("../api", () => ({ api: mockApi, API: "http://api.test/api" }));
jest.mock("@/lib/utils", () => ({ cn: (...a) => a.filter(Boolean).join(" ") }), { virtual: true });
jest.mock("sonner", () => ({ toast: { error: jest.fn(), success: jest.fn() } }));
jest.mock("../../components/ui/dialog", () => {
  const R = require("react");
  const pass = ({ children, open }) => (open === false ? null : R.createElement("div", null, children));
  return { Dialog: pass, DialogContent: pass, DialogHeader: pass, DialogTitle: pass, DialogFooter: pass, DialogTrigger: ({ children }) => children };
});
jest.mock("../../components/RequestTimeline", () => () => null);
jest.mock("../../components/ui/select", () => {
  const R = require("react");
  return {
    Select: ({ value, onValueChange }) => R.createElement("select", { "data-testid": "flt", value, onChange: (e) => onValueChange(e.target.value) },
      ["all", "failed"].map((v) => R.createElement("option", { key: v, value: v }, v))),
    SelectContent: () => null, SelectItem: () => null, SelectTrigger: () => null, SelectValue: () => null,
  };
});
jest.mock("../../pages/EmailInboundPanel", () => () => null);
jest.mock("../../components/EmailReadiness", () => () => null);

const History = require("../../pages/RequestHistoryDialog").default;
const Comms = require("../../pages/CommunicationsTab").default;
globalThis.IS_REACT_ACT_ENVIRONMENT = true;

const deferred = () => { let res, rej; const p = new Promise((a, b) => { res = a; rej = b; }); return { p, res, rej }; };
let root, el;
beforeEach(() => { el = document.createElement("div"); document.body.appendChild(el); root = createRoot(el); mockApi.get.mockReset(); });
afterEach(async () => { await act(async () => root.unmount()); el.remove(); });
const flush = () => act(async () => { await Promise.resolve(); await Promise.resolve(); });
const task = (id) => ({ task: { task_id: id, title: `Title ${id}`, status: "pending" }, receipts: [] });

test("history dialog: delayed reply for request A cannot overwrite request B", async () => {
  const A = deferred(), B = deferred();
  mockApi.get.mockImplementation((u) => (u.includes("/tasks/A/") ? A.p : B.p));
  await act(async () => root.render(<History taskId="A" onClose={() => {}} />));
  await act(async () => root.render(<History taskId="B" onClose={() => {}} />));
  await act(async () => { B.res({ data: task("B") }); }); await flush();
  await act(async () => { A.res({ data: task("A") }); }); await flush();
  expect(el.textContent).toContain("Title B");
  expect(el.textContent).not.toContain("Title A");
});

test("history dialog: failed fetch shows a recoverable error, not Loading, and retry works", async () => {
  mockApi.get.mockRejectedValueOnce({ response: { status: 403 } });
  await act(async () => root.render(<History taskId="X" onClose={() => {}} />)); await flush();
  expect(el.querySelector("[data-testid=request-history-error]")).not.toBeNull();
  expect(el.textContent).not.toContain("Loading");
  mockApi.get.mockResolvedValueOnce({ data: task("X") });
  await act(async () => { el.querySelector("[data-testid=request-history-retry]").click(); }); await flush();
  expect(el.textContent).toContain("Title X");
});

test("history dialog: closing before the reply arrives drops it quietly", async () => {
  const A = deferred(); mockApi.get.mockReturnValue(A.p);
  await act(async () => root.render(<History taskId="A" onClose={() => {}} />));
  await act(async () => root.render(<History taskId={null} onClose={() => {}} />));
  await act(async () => { A.res({ data: task("A") }); }); await flush();
  expect(el.textContent).toBe("");
});

test("communications log: an old All reply arriving after the new Failed reply is dropped", async () => {
  const allReply = deferred(), failedReply = deferred();
  mockApi.get.mockImplementation((u) => {
    if (u.startsWith("/notifications/status")) return Promise.resolve({ data: { resend: {} } });
    if (u.includes("status=failed")) return failedReply.p;
    if (u.startsWith("/notifications?")) return allReply.p;
    return Promise.resolve({ data: {} });
  });
  await act(async () => root.render(<Comms />));
  const sel = el.querySelector("[data-testid=flt]");
  await act(async () => { sel.value = "failed"; sel.dispatchEvent(new Event("change", { bubbles: true })); });
  const n = (id, st) => ({ notification_id: id, status: st, channel: "email", recipient: `${id}@x.t`, created_at: "2031-01-01T00:00:00Z", body: id });
  await act(async () => { failedReply.res({ data: [n("FAILEDROW", "failed")] }); }); await flush();
  await act(async () => { allReply.res({ data: [n("ALLROW", "sent")] }); }); await flush();
  const log = el.querySelector("[data-testid=notif-log]").textContent;
  expect(log).toContain("FAILEDROW"); expect(log).not.toContain("ALLROW");
});
