import React, { act } from "react";
import { createRoot } from "react-dom/client";

jest.mock("@/lib/utils", () => ({ cn: (...values) => values.filter(Boolean).join(" ") }), { virtual: true });
jest.mock("react-router-dom", () => ({
  Link: ({ to, children, ...rest }) => <a href={to} {...rest}>{children}</a>,
}), { virtual: true });
jest.mock("../../lib/auth", () => ({ useAuth: () => ({ user: null }) }));
jest.mock("../../components/capabilities/CapabilityPanel", () => ({ capability }) => (
  capability ? <div data-testid="panel">{capability.name}</div> : null));
jest.mock("../../components/landing/ExperienceVideoLibrary", () => () => null);

import Landing from "../Landing";
import { ALL_CAPABILITIES } from "../../lib/capabilities";
import { statusOf } from "../../lib/capabilities/status";

globalThis.IS_REACT_ACT_ENVIRONMENT = true;

async function render() {
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  await act(async () => root.render(<Landing />));
  return { host, done: async () => { await act(async () => root.unmount()); host.remove(); } };
}

test("public paths, staff sign in, and every product picture says whose data it shows", async () => {
  const { host, done } = await render();
  const hrefs = new Set([...host.querySelectorAll("a")].map((a) => a.getAttribute("href")));
  for (const to of ["/for-residents", "/for-communities", "/experience", "/kiosk/demo", "/login"]) expect(hrefs).toContain(to);
  expect(host.textContent).toMatch("Staff sign in");
  const imgs = [...host.querySelectorAll("figure img")];
  expect(imgs.length).toBeGreaterThanOrEqual(6);
  for (const img of imgs) {
    expect(img.getAttribute("src")).toMatch(/^\/media\/(screens|illustrations)\//);
    const caption = img.closest("figure").querySelector("figcaption").textContent;
    // every picture says what it is; every product screen also says whose data it shows
    expect(caption).toMatch(/CAOSCare screen|Illustration|Concept/);
    if (img.getAttribute("src").startsWith("/media/screens/")) expect(caption).toMatch(/simulated|sample/);
  }
  await done();
});

test("status board lists every public capability under its registry status and opens its panel", async () => {
  const { host, done } = await render();
  for (const c of ALL_CAPABILITIES) {
    const chip = host.querySelector(`[data-testid=status-${c.id}]`);
    expect(chip.textContent).toBe(c.name);
    expect(chip.closest("[data-status]").dataset.status).toBe(statusOf(c.id));
  }
  await act(async () => host.querySelector("[data-testid=status-voice]").click());
  expect(host.querySelector("[data-testid=panel]").textContent).toBe("Talk to Aria");
  await done();
});
