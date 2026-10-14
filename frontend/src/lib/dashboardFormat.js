// Shared wording for the Live Operations dashboard (SIM-007A).

export const titleCase = (value) => String(value || "").replaceAll("_", " ");

export const simTime = (t) => (t ? `Day ${t.day} · ${t.hh_mm}` : "—");

export function minutes(value) {
  if (value === null || value === undefined) return "—";
  const hours = Math.floor(value / 60);
  return hours ? `${hours} h ${value % 60} min` : `${value} min`;
}

export const STATUS_LABEL = {
  pending: "Waiting",
  in_progress: "In progress",
  completed: "Completed",
  skipped: "Skipped",
};

export const STATUS_CLASS = {
  pending: "border-caos-amber text-[#8B5A20]",
  in_progress: "border-caos-moss text-caos-forest",
  completed: "border-caos-line text-caos-mute",
};

export const DUTY_LABEL = {
  on_duty: "On duty",
  on_call: "On call",
  off_duty: "Off duty",
  closed: "Closed",
  uncovered: "UNCOVERED",
  simulation_complete: "Complete",
};

export const AVAILABILITY_LABEL = {
  busy: "Busy",
  free: "Free",
  covered: "Covered",
  on_call: "On call",
  off_duty: "Off duty",
};

// Simulated minutes per real second between two polls, as an "N×" pace.
export function observedPace(previous, current) {
  if (!previous || !current) return null;
  const sim = (current.minute ?? 0) - (previous.minute ?? 0);
  const real = (current.at - previous.at) / 1000;
  if (real < 1 || sim < 0) return null;
  return Math.round((sim * 60) / real);
}
