// Split out of Admin.jsx to keep that file under the repo's 300-line cap -
// pure data, no JSX/hooks. Grouped so the tab bar reads as categories
// instead of one flat row of 20+ items - "Communication & requests" is the
// priority group (Michael: "pendants and devices will be last, we will get
// the communication... seamless first"), "Devices & hardware" is
// deliberately last.
export function tabGroups(residents, staff, kiosks, zones, user) {
  return [
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
        { value: "departments", label: "Departments" },
      ],
    },
    {
      id: "facility",
      label: "Facility & staff",
      tabs: [
        { value: "staff", label: `Staff (${staff.length})` },
        { value: "zones", label: `Zones (${zones.length})` },
        { value: "map", label: "Map" },
        ...(user?.role === "owner" ? [{ value: "facilities", label: "Facilities" }] : []),
      ],
    },
    {
      id: "devices",
      label: "Devices & hardware",
      tabs: [
        { value: "pendants", label: "Pendants" },
        { value: "rf", label: "RF Pendants" },
        { value: "wearables", label: "Wearables" },
        { value: "devices", label: "Smart devices" },
        { value: "kiosks", label: `Kiosks (${kiosks.length})` },
        { value: "tokens", label: "Device tokens" },
        { value: "hardware", label: "Hardware" },
      ],
    },
    {
      id: "reports",
      label: "Reports",
      tabs: [
        { value: "insights", label: "Insights" },
        { value: "audit", label: "Audit" },
        { value: "escalation", label: "Escalation" },
        { value: "roadmap", label: "Roadmap" },
      ],
    },
  ];
}
