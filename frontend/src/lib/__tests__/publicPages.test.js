import React, { act } from "react";
import fs from "fs";
import path from "path";
import { createRoot } from "react-dom/client";
import { PUBLIC_PAGES, canonicalUrl } from "../publicPages";
import usePageMeta from "../../components/public/usePageMeta";

// Findability: each public page names itself (title, description, canonical
// address, share tags), and the sitemap lists exactly those pages.
globalThis.IS_REACT_ACT_ENVIRONMENT = true;
const PUBLIC = path.join(__dirname, "..", "..", "..", "public");

function Probe({ at }) {
  usePageMeta(at);
  return null;
}

async function visit(at) {
  const host = document.createElement("div");
  const root = createRoot(host);
  await act(async () => root.render(<Probe at={at} />));
  await act(async () => root.unmount());
}

const head = (sel, attr = "content") => document.head.querySelector(sel)?.getAttribute(attr);

test("sitemap.xml lists exactly the public pages", () => {
  const xml = fs.readFileSync(path.join(PUBLIC, "sitemap.xml"), "utf8");
  const locs = [...xml.matchAll(/<loc>([^<]+)<\/loc>/g)].map((m) => m[1]).sort();
  expect(locs).toEqual(Object.keys(PUBLIC_PAGES).map(canonicalUrl).sort());
});

test.each(Object.keys(PUBLIC_PAGES))("%s gets its own title, description and canonical address", async (at) => {
  await visit(at);
  const page = PUBLIC_PAGES[at];
  expect(document.title).toBe(page.title);
  expect(head('meta[name="description"]')).toBe(page.description);
  expect(head('link[rel="canonical"]', "href")).toBe(canonicalUrl(at));
  expect(head('meta[property="og:url"]')).toBe(canonicalUrl(at));
  expect(head('meta[property="og:title"]')).toBe(page.title);
  expect(document.head.querySelectorAll('link[rel="canonical"]')).toHaveLength(1);
});

test("index.html does not pin one canonical address on every page", () => {
  const html = fs.readFileSync(path.join(PUBLIC, "index.html"), "utf8");
  expect(html).not.toMatch(/rel="canonical"/);
  expect(html).not.toMatch(/og:url/);
  expect(html).toMatch(/og:image" content="https:\/\/caoscare\.com\/og-image\.jpg"/);
  expect(fs.existsSync(path.join(PUBLIC, "og-image.jpg"))).toBe(true);
  const ld = html.match(/<script type="application\/ld\+json">([^<]+)<\/script>/);
  expect(JSON.parse(ld[1])["@graph"].map((n) => n["@type"])).toEqual(["Organization", "WebSite"]);
});

test("public wording stays within what the site says today", () => {
  const text = Object.values(PUBLIC_PAGES).map((p) => `${p.title} ${p.description}`).join(" ");
  expect(text).not.toMatch(/Planned|In development|Not available yet|kiosk|Home One/i);
  expect(PUBLIC_PAGES["/"].description).toMatch(/In pilot/);
});
