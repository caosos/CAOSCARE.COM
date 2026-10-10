/** Kiosk tile truth: a missing status (RQ-035 strips it for non-admin) is UNKNOWN, never a green "in service". */
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import { kioskSummary, kioskTile } from "../deviceCounts";

let mockRole = "admin"; let mockKiosks; let mockFail = [];
jest.mock("../api", () => ({ api: { get: ((u) => {
  if (u === "/kiosks") return mockKiosks();
  if (mockFail.includes(u)) return Promise.reject(new Error("net"));
  if (u === "/rf/fleet/summary") return Promise.resolve({ data: { total: 2, in_service: 2, need_attention: 0, devices: [] } });
  return Promise.resolve({ data: [] });
}) } }));
jest.mock("../auth", () => ({ useAuth: () => ({ user: { role: mockRole } }) }));
jest.mock("react-router-dom", () => ({ Link: ({ children }) => children }), { virtual: true });
jest.mock("@/lib/utils", () => ({ cn: (...a) => a.filter(Boolean).join(" ") }), { virtual: true });
const Card = require("../../pages/DeviceStatusCard").default;
globalThis.IS_REACT_ACT_ENVIRONMENT = true;

let root, el;
beforeEach(() => { mockFail = []; el = document.createElement("div"); document.body.appendChild(el); root = createRoot(el); });
afterEach(async () => { await act(async () => root.unmount()); el.remove(); });
const flush = () => act(async () => { for (let i = 0; i < 20; i++) await Promise.resolve(); await new Promise((r) => setTimeout(r, 0)); });
const tile = async (role, kiosks) => {
  mockRole = role; mockKiosks = typeof kiosks === "function" ? kiosks : () => Promise.resolve({ data: kiosks });
  await act(async () => root.render(<Card />)); await flush();
  return el.querySelector("[data-testid=inv-kiosks]");
};
const admin = [{ kiosk_id: "a", room: "1", status: "online" }, { kiosk_id: "b", room: "2", status: "online" }];
const stripped = [{ kiosk_id: "a", room: "1" }, { kiosk_id: "b", room: "2" }];

test("admin, all known online: 2 / 2 in service, healthy", async () => {
  const t = await tile("admin", admin);
  expect(t.textContent).toContain("2"); expect(t.textContent).toContain("/ 2 in service"); expect(t.className).toContain("border-caos-moss");
});
test("admin with one offline: counts it, not healthy, says offline", async () => {
  const t = await tile("admin", [...admin, { kiosk_id: "c", room: "3", status: "offline" }]);
  expect(t.textContent).toContain("/ 3 in service"); expect(t.textContent).toContain("1 offline"); expect(t.className).not.toContain("border-caos-moss");
});
test("non-admin stripped rows: NOT green, no 'in service' claim, says status not available", async () => {
  const t = await tile("staff", stripped);
  expect(t.textContent).toContain("status not available to your role"); expect(t.textContent).not.toContain("in service");
  expect(t.className).not.toContain("border-caos-moss"); expect(t.textContent).toContain("—");
});
test("admin with missing/unrecognized status: says status unknown, no permission claim, not green", async () => {
  const t = await tile("admin", [{ kiosk_id: "a", room: "1" }, { kiosk_id: "b", room: "2", status: "banana" }]);
  expect(t.textContent).toContain("status unknown"); expect(t.textContent).not.toContain("your role");
  expect(t.textContent).not.toContain("in service"); expect(t.className).not.toContain("border-caos-moss");
});
test("RF fleet request failure: pendants tile unavailable, not 0 / 0 or green", async () => {
  mockFail = ["/rf/fleet/summary"];
  await tile("admin", admin);
  const t = el.querySelector("[data-testid=inv-pendants]");
  expect(t.textContent).toContain("unavailable"); expect(t.textContent).not.toContain("0 in service"); expect(t.className).not.toContain("border-caos-moss");
});
test("RF fleet loaded: pendants tile shows real counts", async () => {
  await tile("admin", admin);
  expect(el.querySelector("[data-testid=inv-pendants]").textContent).toContain("2 in service");
});
test("wearables request failure: tile unavailable", async () => {
  mockFail = ["/wearables"];
  await tile("admin", admin);
  expect(el.querySelector("[data-testid=inv-wearables]").textContent).toContain("unavailable");
});
test("activity request failure: says unavailable, not 'No device activity yet'", async () => {
  mockFail = ["/alerts"];
  await tile("admin", admin);
  expect(el.textContent).toContain("Device activity unavailable"); expect(el.textContent).not.toContain("No device activity yet");
});
test("activity loaded and empty: says no activity", async () => {
  await tile("admin", admin);
  expect(el.textContent).toContain("No device activity yet");
});
test("mixed known and unknown: counts only known online, flags unknown, not healthy", async () => {
  const t = await tile("admin", [{ kiosk_id: "a", room: "1", status: "online" }, { kiosk_id: "b", room: "2" }]);
  expect(t.textContent).toContain("1"); expect(t.textContent).toContain("/ 2 in service"); expect(t.textContent).toContain("1 status unknown"); expect(t.className).not.toContain("border-caos-moss");
});
test("empty list: 0 / 0, not healthy", async () => {
  const t = await tile("admin", []);
  expect(t.textContent).toContain("/ 0 kiosks"); expect(t.className).not.toContain("border-caos-moss");
});
test("failed request: unavailable, not 0 / 0", async () => {
  const f = await tile("admin", () => Promise.reject(new Error("net")));
  expect(f.textContent).toContain("status unavailable"); expect(f.textContent).not.toContain("/ 0");
});
test("pure helpers", () => {
  expect(kioskSummary(stripped)).toMatchObject({ total: 2, known: 0, unknown: 2 });
  expect(kioskTile(kioskSummary(admin)).healthy).toBe(true);
  expect(kioskTile(kioskSummary(null, false)).healthy).toBe(false);
});
