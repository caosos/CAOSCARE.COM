import React, { act } from "react";
import { createRoot } from "react-dom/client";

jest.mock("@/lib/utils", () => ({ cn: (...values) => values.filter(Boolean).join(" ") }), { virtual: true });
jest.mock("react-router-dom", () => ({
  Link: ({ to, children, ...rest }) => <a href={to} {...rest}>{children}</a>,
}), { virtual: true });
jest.mock("../../lib/auth", () => ({ useAuth: () => ({ user: null }) }));
jest.mock("../../components/capabilities/CapabilityPanel", () => ({ capability }) => (
  capability ? <div data-testid="panel">{capability.name}</div> : null));
jest.mock("../../components/landing/ExperienceVideoLibrary", () => ({ __esModule: true, default: () => null, ExperienceVideo: ({ video }) => <div data-testid="video">{video.title}</div> }));

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
    expect(img.getAttribute("src")).toMatch(/^\/media\/(screens|illustrations|concepts)\//);
    const caption = img.closest("figure").querySelector("figcaption").textContent;
    // every picture says what it is; every product screen also says whose data it shows
    expect(caption).toMatch(/CAOSCare screen|Illustration|Design concept/);
    if (img.getAttribute("src").startsWith("/media/screens/")) expect(caption).toMatch(/simulated|sample/);
    if (img.getAttribute("src").startsWith("/media/concepts/")) expect(caption).toMatch("Design concept · not built or tested");
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

test("owner message order: Aria the helper, everyday room life, community help, then the platform proof", async () => {
  // #162 owner direction 2026-10-16 (c6209415088, c6209371153)
  const { host, done } = await render();
  expect(host.querySelector("h1").textContent).toBe("Aria — your personal helper.");
  expect(host.querySelector("[data-testid=hero-video]").textContent).toMatch("Aria — your personal helper");
  const order = ["tiles-room", "tiles-community", "request-journey", "staff-showcase"]
    .map((id) => [...host.querySelectorAll("[data-testid]")].findIndex((e) => e.dataset.testid === id));
  expect(order.every((v, i) => v >= 0 && (i === 0 || v > order[i - 1]))).toBe(true);
  // every tile shows its registry status, never a benchmark claim
  for (const tile of host.querySelectorAll("[data-testid^=tile-]")) {
    expect(tile.querySelector("[data-status]").dataset.status).toBe(statusOf(tile.dataset.testid.slice(5)));
  }
  await done();
});

test("Home One is shown only as a labelled design concept, after what works today", async () => {
  // Owner 2026-10-23: showcase Home One; it is not built, so it is never a capability or status.
  const { host, done } = await render();
  const section = host.querySelector("#home-one");
  expect(section.textContent).toMatch("none has been built or tested yet");
  expect(section.querySelector("figcaption").textContent).toMatch("Design concept · not built or tested");
  expect(host.querySelector("[data-testid=landing-status]").compareDocumentPosition(section) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  expect(host.querySelector("[data-testid=status-home_one]")).toBeNull();
  await done();
});
