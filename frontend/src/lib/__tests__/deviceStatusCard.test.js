/** Kiosk tile truth: a missing status (RQ-035 strips it for non-admin) is UNKNOWN, never a green "in service". */
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import { kioskSummary, kioskTile } from "../deviceCounts";

let mockRole = "admin"; let mockKiosks;
jest.mock("../api", () => ({ api: { get: ((u) => {
  if (u === "/kiosks") return mockKiosks();
  if (u === "/rf/fleet/summary") return Promise.resolve({ data: { total: 0, in_service: 0, need_attention: 0, devices: [] } });
  return Promise.resolve({ data: [] });
}) } }));
jest.mock("../auth", () => ({ useAuth: () => ({ user: { role: mockRole } }) }));
jest.mock("react-router-dom", () => ({ Link: ({ children }) => children }), { virtual: true });
jest.mock("@/lib/utils", () => ({ cn: (...a) => a.filter(Boolean).join(" ") }), { virtual: true });
const Card = require("../../pages/DeviceStatusCard").default;
globalThis.IS_REACT_ACT_ENVIRONMENT = true;

let root, el;
beforeEach(() => { el = document.createElement("div"); document.body.appendChild(el); root = createRoot(el); });
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
