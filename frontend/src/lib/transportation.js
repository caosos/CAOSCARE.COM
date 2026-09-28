// Pure helpers for the transportation screens (calendar, driver config,
// staff ride forms). No server calls here - the booking engine on the
// backend (transportation_engine.py) is the only place that decides whether
// a ride is booked; these only describe what it returned.

// Python weekday numbers (0 = Monday), matching TransportDriver.work_days.
export const WEEKDAYS = [
  [0, "Mon"], [1, "Tue"], [2, "Wed"], [3, "Thu"], [4, "Fri"], [5, "Sat"], [6, "Sun"],
];

export function driverHoursLabel(driver) {
  if (!driver) return "";
  const days = driver.work_days;
  const hasDays = Array.isArray(days);
  const hasShift = driver.shift_start || driver.shift_end;
  if (!hasDays && !hasShift) return "No hours set - available any time";
  const dayText = !hasDays ? "Every day"
    : days.length === 0 ? "No working days"
    : WEEKDAYS.filter(([n]) => days.includes(n)).map(([, l]) => l).join(" ");
  const shiftText = hasShift ? ` · ${driver.shift_start || "start of day"}–${driver.shift_end || "end of day"}` : "";
  return `${dayText}${shiftText}`;
}

const RIDER_OPEN = ["pending", "in_progress"];

export function isRiderOpen(rider) {
  return RIDER_OPEN.includes(rider?.status);
}

// Which staff actions a run shows. canOperate = front desk, admin, or a
// transportation-department staff member (the backend enforces the same).
export function runActions(run, { canOperate = false } = {}) {
  const openRiders = (run?.riders || []).filter(isRiderOpen);
  if (!canOperate || !["confirmed", "in_progress"].includes(run?.status) || openRiders.length === 0) {
    return { depart: false, complete: false };
  }
  return { depart: run.status === "confirmed", complete: true };
}

export function riderStatusLabel(rider) {
  if (rider?.status === "completed") return "Ride completed";
  if (rider?.status === "skipped") return "Cancelled";
  if (rider?.status === "in_progress") return "On the ride";
  return "Booked";
}

export function runStatusLabel(run) {
  if (run?.status === "in_progress") return `Departed${run.closed_by_name ? ` · ${run.closed_by_name}` : ""}`;
  if (run?.status === "completed") return "Completed";
  if (run?.status === "cancelled") return "Cancelled";
  return "Confirmed";
}

// "HH:MM" from an <input type="time"> is already 24h; empty means "no time
// committed yet", which the backend treats as a request without a booking.
export function cleanTime(value) {
  return /^\d{2}:\d{2}$/.test(value || "") ? value : null;
}

export function todayLocal(d = new Date()) {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

// What Aria says for check_transportation_status - built only from the
// fields GET /transportation/request/status returns, never inferred. A
// booked ride is a confirmed pickup; it is never "someone is on the way"
// until staff mark the ride departed.
export function transportStatusMessage(data) {
  if (!data?.found) return "no transportation request found on record.";
  const what = data.purpose ? `the ride for ${data.purpose}` : "the ride";
  const day = data.run?.date || data.requested_for_date;
  if (data.status === "skipped") {
    return `${what} on ${day} was cancelled${data.cancel_reason ? ` - reason noted: ${data.cancel_reason}` : ""}.`;
  }
  if (data.status === "completed") return `${what} on ${day} is marked completed.`;
  if (data.booked && data.run) {
    const who = [data.run.driver_name && `driver ${data.run.driver_name}`, data.run.vehicle_name].filter(Boolean).join(", ");
    if (data.run.status === "in_progress") return `${what} on ${day} has been marked departed by staff (pickup was ${data.run.depart_time}).`;
    return `confirmed - ${what}: pickup at ${data.run.depart_time} on ${day}${who ? ` (${who})` : ""}.`;
  }
  if (data.booked) return `booked for ${data.slot?.start_time} on ${day}.`;
  return `still waiting - ${what} is requested for ${day}${data.requested_for_time_label ? ` (${data.requested_for_time_label})` : ""}, no confirmed pickup time yet; the front desk coordinates it.`;
}
