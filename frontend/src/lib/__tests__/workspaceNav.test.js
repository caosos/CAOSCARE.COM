import { NAV_SECTIONS, navFor, sectionOfTab } from "../workspaceNav";
import { tabGroups } from "../adminTabGroups";

const owner = { role: "owner" };
const allAdminTabs = (user) => tabGroups([], [], [], [], user).flatMap((g) => g.tabs.map((t) => t.value));

test("every command-centre tab is reachable from the workspace sidebar", () => {
  const linked = new Set(NAV_SECTIONS.flatMap((s) => s.items.map((i) => i.tab).filter(Boolean)));
  const missing = allAdminTabs(owner).filter((t) => !linked.has(t));
  expect(missing).toEqual([]);
});

test("every sidebar tab link names a real command-centre tab", () => {
  const real = new Set(allAdminTabs(owner));
  for (const s of NAV_SECTIONS) for (const i of s.items) if (i.tab) expect(real.has(i.tab)).toBe(true);
});

test("the approved sidebar order, with Ask Aria directly beneath Settings", () => {
  expect(NAV_SECTIONS.map((s) => s.label)).toEqual(["Dashboard", "Residents", "Staff", "Tasks", "Schedules",
    "Departments", "Reports", "Devices", "Settings", "Ask Aria"]);
});

test("owner-only destinations are hidden from admins", () => {
  const adminItems = navFor("admin").flatMap((s) => s.items.map((i) => i.to));
  expect(adminItems).not.toContain("/admin?tab=facilities");
  expect(adminItems).not.toContain("/admin/blueprint");
  expect(adminItems).not.toContain("/aria");
  expect(allAdminTabs({ role: "admin" })).not.toContain("facilities");   // the classic page agrees
  const ownerItems = navFor("owner").flatMap((s) => s.items.map((i) => i.to));
  expect(ownerItems).toEqual(expect.arrayContaining(["/admin?tab=facilities", "/admin/blueprint", "/aria"]));
});

test("staff roles get no admin navigation", () => {
  expect(navFor("staff")).toEqual([]);
});

test("pages outside the command centre stay reachable", () => {
  const pages = NAV_SECTIONS.flatMap((s) => s.items.map((i) => i.to));
  for (const p of ["/staff", "/alerts", "/front-desk", "/workspace", "/admin/install", "/admin/help", "/admin"]) {
    expect(pages).toContain(p);
  }
  expect(sectionOfTab("nursing")).toBe("departments");
});
