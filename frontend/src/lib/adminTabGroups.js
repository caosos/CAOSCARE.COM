// Split out of Admin.jsx to keep that file under the 300-line cap - pure
// data, no JSX/hooks. Grouped as the Owner/Admin COMMUNITY COMMAND CENTRE:
// the top-level groups are real responsibilities, not a flat row of 25 tabs.
// Owner lands on "Community" (Operations overview), then moves down into
// residents, departments/staff, requests, devices, reports, users/access,
// facility setup.
export function tabGroups(residents, staff, kiosks, zones, user) {
  return [
    {
      id: "community",
      label: "Community",
      tabs: [
        { value: "overview", label: "Operations overview" },
        { value: "alerts", label: "Alerts & events" },
        { value: "maintenance", label: "Maintenance" },
      ],
    },
    {
      id: "residents",
      label: "Residents & care",
      tabs: [
        { value: "residents", label: `Residents (${residents.length})` },
        { value: "clinician", label: "Clinician" },
        { value: "family", label: "Family" },
        { value: "meds", label: "Meds" },
      ],
    },
    {
      id: "departments",
      label: "Departments & staff",
      tabs: [
        { value: "departments", label: "Departments" },
        { value: "staff", label: "Users & access" },
        { value: "zones", label: `Zones (${zones.length})` },
        { value: "map", label: "Map" },
      ],
    },
    {
      id: "communication",
      label: "Communication & requests",
      tabs: [
        { value: "requests", label: "Requests" },
        { value: "tasks", label: "Tasks" },
        { value: "schedule", label: "Schedule" },
        { value: "menu", label: "Menu" },
        { value: "transportation", label: "Transportation" },
        { value: "transport-calendar", label: "Transport calendar" },
        { value: "transport-resources", label: "Transport resources" },
      ],
    },
    {
      id: "devices",
      label: "Devices",
      tabs: [
        { value: "rf", label: "Pendants" },
        { value: "wearables", label: "Wearables" },
        { value: "devices", label: "Smart devices" },
        { value: "kiosks", label: `Kiosks (${kiosks.length})` },
        { value: "tokens", label: "Device tokens" },
        { value: "hardware", label: "Hardware" },
      ],
    },
    {
      id: "reports",
      label: "Reports & audit",
      tabs: [
        { value: "reports", label: "Ops reports" },
        { value: "activity", label: "Activity log" },
        { value: "insights", label: "Insights" },
        { value: "audit", label: "Audit" },
        { value: "escalation", label: "Escalation" },
        { value: "roadmap", label: "Roadmap" },
      ],
    },
    ...(user?.role === "owner"
      ? [{
          id: "facility",
          label: "Facility setup",
          tabs: [{ value: "facilities", label: "Facilities" }],
        }]
      : []),
  ];
}

// External deep-links (staff dashboard cards, Admin Aria, notifications)
// use /admin?tab=<value>. A couple of friendly aliases so a link can say
// ?tab=users or ?tab=pendants.
export const TAB_ALIASES = {
  users: "staff",
  pendants: "rf",
  "resident-search": "residents",
};

export function resolveTab(value, groups) {
  const v = TAB_ALIASES[value] || value;
  return groups.some((g) => g.tabs.some((t) => t.value === v)) ? v : null;
}
