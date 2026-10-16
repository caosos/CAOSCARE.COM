import React, { act } from "react";
import fs from "fs";
import path from "path";
import { createRoot } from "react-dom/client";

// #162: the public site is one system. Every public page renders in the shared
// shell, links only to real public destinations, shows existing current media,
// and uses none of the retired gray/tan/orange/pink palette.
jest.mock("@/lib/utils", () => ({ cn: (...values) => values.filter(Boolean).join(" ") }), { virtual: true });
jest.mock("react-router-dom", () => ({
  Link: ({ to, children, ...rest }) => <a href={to} {...rest}>{children}</a>,
  useLocation: () => ({ hash: "" }),
}), { virtual: true });
jest.mock("../../lib/auth", () => ({ useAuth: () => ({ user: null }) }));
jest.mock("../../components/capabilities/CapabilityPanel", () => () => null);

import Landing from "../Landing";
import ForResidents from "../ForResidents";
import ForCommunities from "../ForCommunities";
import RoomExperience from "../RoomExperience";
import RoomScreenPreview from "../../components/public/RoomScreenPreview";
import DemoSiteBar from "../../components/kiosk/demo/DemoSiteBar";
import { PUBLIC_LINKS } from "../../components/landing/LandingNav";
import { SCREENS } from "../../lib/capabilities/visuals";

globalThis.IS_REACT_ACT_ENVIRONMENT = true;
const PUBLIC = path.join(__dirname, "..", "..", "..", "public");
const ROUTES = new Set(["/", "/for-residents", "/for-communities", "/experience", "/kiosk/demo", "/login"]);

async function render(Page) {
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  await act(async () => root.render(<Page />));
  return { host, done: async () => { await act(async () => root.unmount()); host.remove(); } };
}

const PAGES = { Landing, ForResidents, ForCommunities, RoomExperience, RoomScreenPreview };

describe.each(Object.entries(PAGES))("%s", (name, Page) => {
  test("uses the shared public shell, real destinations and existing current media", async () => {
    const { host, done } = await render(Page);
    for (const l of PUBLIC_LINKS) expect(host.querySelector(`[data-testid=${l.testid}]`).getAttribute("href")).toBe(l.to);
    expect(host.textContent).toMatch("Staff sign in");
    for (const a of host.querySelectorAll("a[href]")) {
      const href = a.getAttribute("href");
      if (href.startsWith("#")) { expect([name, href, !!host.querySelector(href)]).toEqual([name, href, true]); continue; }
      if (href.startsWith("/media/")) { expect([href, fs.existsSync(path.join(PUBLIC, href))]).toEqual([href, true]); continue; }
      expect([name, href, ROUTES.has(href)]).toEqual([name, href, true]);
    }
    for (const img of host.querySelectorAll("img")) {
      const src = img.getAttribute("src");
      expect([src, fs.existsSync(path.join(PUBLIC, src))]).toEqual([src, true]);
      expect(img.getAttribute("alt").length).toBeGreaterThan(10);
    }
    expect([name, host.querySelectorAll('[class*="caos-"], [class*="font-display"]').length]).toEqual([name, 0]);
    expect(host.textContent).not.toMatch(/kiosk/i);
    // Owner 2026-10-16: no public page shows a Planned or In development capability.
    expect([name, host.textContent.match(/\b(Planned|In development|Not available yet)\b/)]).toEqual([name, null]);
    await done();
  });
});

test("low vision is shown with the real high-contrast and enlarged room screen", async () => {
  const { host, done } = await render(ForResidents);
  const proof = host.querySelector("[data-testid=low-vision-proof]");
  const srcs = [...proof.querySelectorAll("img")].map((i) => i.getAttribute("src"));
  expect(srcs).toEqual(expect.arrayContaining([SCREENS.roomContrast.src, SCREENS.roomEnlarged.src]));
  await done();
});

test("staff response uses the current Operations screens, not the retired command centre", async () => {
  for (const Page of [Landing, ForCommunities, ForResidents]) {
    const { host, done } = await render(Page);
    const srcs = [...host.querySelectorAll("[data-testid=staff-showcase] img")].map((i) => i.getAttribute("src"));
    expect(srcs[0]).toBe(SCREENS.workspace.src);
    await done();
  }
});

test("the room screen demo never dead-ends: with no demo room switched on it shows the real screens", async () => {
  const { host, done } = await render(RoomScreenPreview);
  expect(host.textContent).toMatch("The live demo room isn't switched on at this site right now.");
  expect(host.querySelectorAll("img").length).toBe(3);
  await done();
  const kiosk = fs.readFileSync(path.join(__dirname, "..", "Kiosk.jsx"), "utf8");
  expect(kiosk).toMatch("if (demoSetupError) return <RoomScreenPreview />;");
  expect(kiosk).not.toMatch("No public demo kiosk is configured");
});

test("the room screen demo has a way back to the site and shows high contrast as something to try", async () => {
  const toggles = [];
  const Bar = () => <DemoSiteBar highContrast={false} onToggleContrast={() => toggles.push(1)} />;
  const { host, done } = await render(Bar);
  expect(host.querySelector("[data-testid=demo-back-experience]").getAttribute("href")).toBe("/experience");
  expect(host.querySelector("[data-testid=demo-back-home]").getAttribute("href")).toBe("/");
  const hc = host.querySelector("[data-testid=demo-try-contrast]");
  expect(hc.textContent).toMatch(/high contrast/i);
  expect(hc.getAttribute("aria-pressed")).toBe("false");
  await act(async () => hc.click());
  expect(toggles.length).toBe(1);
  await done();
});
