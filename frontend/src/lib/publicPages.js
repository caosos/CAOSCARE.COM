// The public pages search engines and link previews should know about: one
// list for page titles, descriptions and canonical addresses. public/sitemap.xml
// must list exactly these paths (checked by lib/__tests__/publicPages.test.js).
// Keep the wording to what the site itself says: Aria is in pilot.
export const SITE_URL = "https://caoscare.com";

export const PUBLIC_PAGES = {
  "/": {
    title: "CAOSCare — Aria, the voice helper for senior living",
    description:
      "Aria is a room voice helper for senior living, connected to the community's departments: a request reaches the right team, someone owns it, the resident hears its real status, and every step leaves a receipt. In pilot.",
  },
  "/for-residents": {
    title: "Living with Aria — CAOSCare for residents and families",
    description:
      "Just say \"Hey Aria.\" Talk from your chair or bed: Aria answers out loud, sends what you ask for to the right staff, and tells you its real status.",
  },
  "/for-communities": {
    title: "CAOSCare for senior living communities — requests, owners and receipts",
    description:
      "Every resident request reaches the right department with an owner and a clock. Staff, the front desk and leaders see what was requested, claimed, started and finished.",
  },
  "/experience": {
    title: "See your room with CAOSCare — explore a sample apartment",
    description:
      "Aria isn't another tablet for the resident: the room itself becomes the interface. Choose a sample community and apartment and see what CAOSCare adds to it.",
  },
};

export function canonicalUrl(path) {
  return path === "/" ? `${SITE_URL}/` : `${SITE_URL}${path}`;
}
