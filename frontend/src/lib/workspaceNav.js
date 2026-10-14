// Live Operations sidebar: where every existing CAOSCare section lives in
// the new navigation — the one map (old admin tab or page -> sidebar item).
// Admin tabs open the existing command centre at /admin?tab=<value>, so
// nothing was rebuilt or removed; a test checks every admin tab is here.
//
// roles: who may see an entry (the destination route/API still enforces
// its own permission). Default: owner and admin.
const OWNER = ["owner"];

const tab = (value, label, extra = {}) => ({ label, to: `/admin?tab=${value}`, tab: value, ...extra });
const page = (to, label, extra = {}) => ({ label, to, ...extra });

export const NAV_SECTIONS = [
  { id: "dashboard", label: "Dashboard", icon: "House", to: "/operations", items: [
    page("/operations", "My workspace"),
    tab("overview", "Operations overview"),
    tab("live-operations", "Live operations & simulator"),
    tab("alerts", "Alerts & events"),
    tab("routing-exceptions", "Routing exceptions"),
    page("/staff", "Live board"),
    page("/alerts", "Alerts screen"),
  ] },
  { id: "residents", label: "Residents", icon: "UsersRound", to: "/residents", items: [
    page("/residents", "Residents", { tab: "residents" }),   // new design; classic tab: /admin?tab=residents
    tab("clinician", "Clinician"),
    tab("family", "Family"),
    tab("meds", "Medications"),
  ] },
  { id: "staff", label: "Staff", icon: "Users", items: [
    tab("staff", "Users & access"),
    page("/front-desk", "Front desk"),
    page("/workspace", "Department workspace (Work as)"),
  ] },
  { id: "tasks", label: "Tasks", icon: "SquareCheck", items: [
    tab("tasks", "Tasks"),
    tab("requests", "Resident requests"),
  ] },
  { id: "schedules", label: "Schedules", icon: "CalendarDays", items: [
    tab("schedule", "Activity schedule"),
    tab("menu", "Menu"),
    tab("transport-calendar", "Transport calendar"),
    tab("transport-log", "Ride log"),
    tab("transport-resources", "Transport resources"),
  ] },
  { id: "departments", label: "Departments", icon: "Building2", items: [
    tab("departments", "All departments"),
    tab("nursing", "Nursing"),
    tab("maintenance", "Maintenance"),
    tab("housekeeping", "Housekeeping"),
    tab("kitchen", "Kitchen"),
    tab("therapy", "Therapy"),
    tab("activities", "Activities"),
    tab("transportation", "Transportation"),
  ] },
  { id: "reports", label: "Reports", icon: "ChartColumn", items: [
    tab("reports", "Ops reports"),
    tab("activity", "Activity log"),
    tab("insights", "Insights"),
    tab("audit", "Audit"),
  ] },
  { id: "devices", label: "Devices", icon: "Smartphone", items: [
    tab("devices", "Smart devices"),
    tab("rf", "Pendants"),
    tab("wearables", "Wearables"),
    tab("kiosks", "Kiosks"),
    tab("tokens", "Device tokens"),
    tab("hardware", "Hardware"),
    tab("phones", "Phones & calls"),
    tab("zones", "Zones"),
    tab("map", "Map"),
    page("/admin/install", "Install a room screen"),
  ] },
  { id: "settings", label: "Settings", icon: "Settings", items: [
    tab("facilities", "Facilities", { roles: OWNER }),
    tab("communications", "Email & notifications"),
    tab("escalation", "Escalation"),
    tab("roadmap", "Roadmap"),
    page("/admin/blueprint", "Blueprint", { roles: OWNER }),
    page("/admin/help", "Tutorials"),
    page("/admin", "Classic command centre"),
  ] },
  { id: "aria", label: "Ask Aria", icon: "Sparkles", action: "ask-aria", items: [
    page("/aria", "Talk to Aria (voice)", { roles: OWNER }),
  ] },
];

export function canSee(entry, role) {
  return (entry.roles || ["owner", "admin"]).includes(role);
}

// Sections and entries this role may see.
export function navFor(role) {
  return NAV_SECTIONS.filter((s) => canSee(s, role))
    .map((s) => ({ ...s, items: s.items.filter((i) => canSee(i, role)) }));
}

// The section the current page belongs to (active indicator): an exact
// section/page path; command-centre tabs are not pages of this shell.
export function sectionOfPath(pathname) {
  return NAV_SECTIONS.find((s) => s.to === pathname || s.items.some((i) => !i.to.includes("?") && i.to === pathname
    && i.to !== "/admin"))?.id;
}

// The section an admin tab belongs to (for highlighting).
export function sectionOfTab(value) {
  return NAV_SECTIONS.find((s) => s.items.some((i) => i.tab === value))?.id;
}
