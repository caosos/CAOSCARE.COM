// The upcoming schedule (GET /tasks/upcoming, GET /tasks/resident-request/upcoming)
// is already ordered by the backend (facility day, planned time, created). This
// only groups it by day for display and words each row from its own record.
import { rideLine } from "./rideLink";

export const UPCOMING_DEPARTMENTS = ["therapy", "housekeeping"];   // departments whose workspace shows the upcoming view

export function dayLabel(dateIso, todayIso) {
  if (!dateIso) return "Unscheduled";
  if (dateIso === todayIso) return "Today";
  const d = new Date(`${dateIso}T12:00:00`);
  const t = todayIso ? new Date(`${todayIso}T12:00:00`) : null;
  const diff = t ? Math.round((d - t) / 86400000) : null;
  const weekday = d.toLocaleDateString(undefined, { weekday: "long" });
  const md = d.toLocaleDateString(undefined, { month: "long", day: "numeric" });
  if (diff === 1) return `Tomorrow, ${md}`;
  return `${weekday}, ${md}`;
}

/** [{date, label, items}] in the backend's order; items keep their order within a day. */
export function groupByDay(items, todayIso) {
  const out = [];
  for (const it of items || []) {
    const date = it.requested_for_date || it.scheduled_date || null;
    let g = out[out.length - 1];
    if (!g || g.date !== date) { g = { date, label: dayLabel(date, todayIso), items: [] }; out.push(g); }
    g.items.push(it);
  }
  return out;
}

export function timeOf(it) { return it.requested_for_time_label || it.scheduled_time_label || "time not set"; }

/** The ride line for a row, from the ride facts the backend attached (never a guess). */
export function rideLineFor(it) { return it.ride ? rideLine({ linked: true, ride: it.ride }) : null; }

export const LIFECYCLE_LABEL = { open: "Not yet picked up", acknowledged: "Taken on", in_progress: "In progress", resolved: "Done" };
export function lifecycleLabel(it) { return LIFECYCLE_LABEL[it.lifecycle] || it.lifecycle || it.status || ""; }
