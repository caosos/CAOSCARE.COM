import { API } from "./api";

export async function executeTvRemoteSetup(args, ctx) {
  const room = ctx?.room;
  const residentId = ctx?.resident_id;
  if (!room || !residentId || !ctx?.session_id) {
    return { ok: false, message: "TV remote setup needs an active room conversation." };
  }
  const body = {
    phase: args.phase, resident_id: residentId, session_id: ctx.session_id,
    device_id: args.device || null, vendor: args.vendor || null, model: args.model || null,
    setup_id: args.setup_id || null, candidate_id: args.candidate_id || null,
    worked: typeof args.worked === "boolean" ? args.worked : null,
    confirmation_text: ctx.last_user_text || "", turn_suspect: Boolean(ctx.turn_suspect),
  };
  const response = await fetch(`${API}/devices/public/tv-remote-setup`, {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
  });
  const result = await response.json().catch(() => ({}));
  if (!response.ok) return { ok: false, message: result.detail || `couldn't continue TV remote setup (${response.status}).` };
  return result;
}
