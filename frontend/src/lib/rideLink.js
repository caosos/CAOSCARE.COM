// One line about the ride linked to a planned request, from GET /tasks/{id}/ride
// (routes/task_ride_link.py). Says only what the ride's record says: cancelled,
// booked with the real depart time/driver/vehicle, or requested and not yet
// booked. Never "on the way".
export function rideLine(view) {
  const r = view?.ride;
  if (!view?.linked || !r) return null;
  if (r.status === "skipped") return `Ride: cancelled${r.cancel_reason ? ` — ${r.cancel_reason}` : ""}`;
  if (r.status === "completed") return "Ride: completed";
  const when = [r.requested_for_time_label, r.requested_for_date].filter(Boolean).join(" · ");
  if (r.booked && r.run) {
    const who = [r.run.driver_name, r.run.vehicle_name].filter(Boolean).join(", ");
    const state = r.run.status === "departed" ? "departed" : "booked";
    return `Ride: ${state} ${r.run.depart_time}${who ? ` with ${who}` : ""} (${r.run.date})`;
  }
  return `Ride: requested for ${when || "the planned window"}, not yet booked`;
}

// A ride can be asked for once the request has a resident and a planned date
// and no open ride is linked yet.
// Work that comes to the resident's room needs no ride (same list as backend task_ride_link.py).
export const IN_ROOM_DEPARTMENTS = ["housekeeping", "maintenance", "kitchen", "transportation"];

export function canRequestRide(task, view) {
  if (!task?.resident_id || !task?.requested_for_date) return false;
  if (IN_ROOM_DEPARTMENTS.includes(task.visibility_role)) return false;
  if (["completed", "skipped"].includes(task.status)) return false;
  const r = view?.ride;
  return !(view?.linked && r && !["completed", "skipped"].includes(r.status));
}
