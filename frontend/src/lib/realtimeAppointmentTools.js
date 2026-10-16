// check_appointment / note_reported_appointment (backend/routes/appointments.py).
// The backend decides what is verified, reported, in conflict, changed or
// cancelled and writes the receipt; Aria speaks its `spoken` line. Nothing
// here can turn a remembered time into a confirmed one.
import { API } from "./api";

const PATHS = { check_appointment: "check", note_reported_appointment: "report" };

export async function executeAppointmentTool({ name, args, ctx }) {
  const path = PATHS[name];
  if (!path) return undefined;
  if (!ctx?.room && !ctx?.resident_id) return { ok: false, message: "no room context — I can't check that here." };
  const who = { resident_id: ctx.resident_id || null, room: ctx.room || null };
  const body = path === "check"
    ? { ...who, about: args?.about || null, date: args?.date || null, focus: args?.focus || "general" }
    : { ...who, provider: args?.provider || null, date: args?.date, time: args?.time || null,
        time_as_said: args?.time_as_said || null, location: args?.location || null, says_changed: !!args?.says_changed,
        resident_words: args?.resident_words || ctx.last_user_text || null,
        conversation_session_id: ctx.session_id || null };
  let r;
  try {
    r = await fetch(`${API}/appointments/public/${path}`, {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
    });
  } catch {
    r = null;
  }
  if (!r || !r.ok) {
    return { ok: false, message: path === "check"
      ? "I couldn't reach the appointment record just now, so I can't tell you what's on file."
      : "I couldn't save that appointment just now, so nothing was recorded." };
  }
  const d = await r.json();
  return { ok: d.ok !== false, message: d.spoken, found: d.found, recorded: d.recorded, status: d.status || null,
    verified: d.verified ?? null, receipt_id: d.receipt_id || null, appointments: d.appointments || [] };
}
