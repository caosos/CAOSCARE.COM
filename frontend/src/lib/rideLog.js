// Pure helpers for the transportation ride log.
export const LOG_STATUSES = ["waiting", "booked", "departed", "completed", "cancelled"];
export const LOG_STATUS_LABEL = { waiting: "Waiting for a slot", booked: "Booked", departed: "On the road", completed: "Completed", cancelled: "Cancelled" };
export const LOG_STATUS_TONE = {
  waiting: "bg-amber-100 text-amber-900", booked: "bg-blue-100 text-blue-900", departed: "bg-indigo-100 text-indigo-900",
  completed: "bg-green-100 text-green-900", cancelled: "bg-stone-200 text-stone-700",
};
export function logQuery({ from, to, status, q }) {
  const p = new URLSearchParams();
  if (from) p.set("from", from);
  if (to) p.set("to", to);
  if (status) p.set("status", status);
  if (q && q.trim()) p.set("q", q.trim());
  return p.toString();
}
export function pickupLabel(r) {
  if (!r.pickup_time) return "-";
  return `${r.pickup_date || ""} ${r.pickup_time}`.trim();
}

// Only the newest request may update the screen: an older, slower reply must not overwrite it.
export function latestOnly() {
  let n = 0;
  return { next: () => ++n, isCurrent: (id) => id === n };
}
