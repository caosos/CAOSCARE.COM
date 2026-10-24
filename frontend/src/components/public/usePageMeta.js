import { useEffect } from "react";
import { PUBLIC_PAGES, canonicalUrl } from "../../lib/publicPages";

// Sets the page title, description, canonical address and share-preview
// tags for a public page from lib/publicPages.js. index.html carries the
// site-wide defaults; Google renders the app and reads these per page.
function setTag(selector, create, value) {
  let el = document.head.querySelector(selector);
  if (!el) {
    el = create();
    document.head.appendChild(el);
  }
  el.setAttribute(el.tagName === "LINK" ? "href" : "content", value);
}

const meta = (attr, key) => () => {
  const el = document.createElement("meta");
  el.setAttribute(attr, key);
  return el;
};

export default function usePageMeta(path) {
  useEffect(() => {
    const page = PUBLIC_PAGES[path];
    if (!page) return;
    const url = canonicalUrl(path);
    document.title = page.title;
    setTag('meta[name="description"]', meta("name", "description"), page.description);
    setTag('link[rel="canonical"]', () => {
      const el = document.createElement("link");
      el.setAttribute("rel", "canonical");
      return el;
    }, url);
    setTag('meta[property="og:title"]', meta("property", "og:title"), page.title);
    setTag('meta[property="og:description"]', meta("property", "og:description"), page.description);
    setTag('meta[property="og:url"]', meta("property", "og:url"), url);
  }, [path]);
}
