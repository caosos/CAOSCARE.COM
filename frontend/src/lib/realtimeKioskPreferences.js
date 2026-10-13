import { API } from "./api";

/** Durable room preferences spoken through Resident Aria.
 * The backend owns the pending proposal and refuses a confirmed write unless
 * the same live session first requested it and the current turn is affirmative.
 */
export async function executeKioskPreferenceTool({ name, args, ctx }) {
  if (name !== "set_tv_audio_duck") return undefined;
  if (!ctx?.kiosk_id || !ctx?.resident_id || !ctx?.session_id) {
    return { ok: false, message: "I can't change that setting without an active room session." };
  }
  if (ctx?.turn_suspect) {
    return { ok: false, message: "I want to make sure I heard you correctly. Could you say that again?" };
  }
  const r = await fetch(`${API}/kiosks/${encodeURIComponent(ctx.kiosk_id)}/tv-audio-duck/voice`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      resident_id: ctx.resident_id,
      session_id: ctx.session_id,
      enabled: args.enabled === true,
      confirmed: args.confirmed === true,
      request_text: args.confirmed === true ? null : (ctx.last_user_text || ""),
      confirmation_text: args.confirmed === true ? (ctx.last_user_text || "") : null,
    }),
  });
  const data = await r.json().catch(() => ({}));
  if (!r.ok) return { ok: false, message: data?.detail || "I couldn't save that setting." };
  return data;
}
