// check_medication_status (backend/routes/medication_status.py): the backend
// reads the schedule and the open nursing request, and files the high-priority
// nursing request itself when nothing is confirmed. Aria speaks its `spoken`
// line; nothing here can claim that someone is on the way.
import { API } from "./api";

export async function executeMedicationTool({ name, args, ctx }) {
  if (name !== "check_medication_status") return undefined;
  if (!ctx?.room && !ctx?.resident_id) return { ok: false, message: "no room context — I can't check that here." };
  let r;
  try {
    r = await fetch(`${API}/medications/public/status-check`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        resident_id: ctx.resident_id || null, room: ctx.room || null,
        resident_words: args?.resident_words || ctx.last_user_text || null,
        conversation_session_id: ctx.session_id || null,
      }),
    });
  } catch {
    r = null;
  }
  if (!r || !r.ok) {
    return { ok: false, message: "I couldn't check or reach nursing just now, so nothing was sent. If you need someone, press your call button." };
  }
  const d = await r.json();
  return { ok: true, message: d.spoken, staff_confirmed: d.staff_confirmed, task_id: d.task_id || null,
    receipt_id: d.receipt_id || null, scheduled_today: d.scheduled_today || [] };
}
